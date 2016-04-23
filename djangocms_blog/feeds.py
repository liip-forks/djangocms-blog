# -*- coding: utf-8 -*-
from __future__ import absolute_import, print_function, unicode_literals

from django.core.cache import cache
from django.utils.encoding import force_text
from django.utils.feedgenerator import Rss201rev2Feed, rfc2822_date

from aldryn_apphooks_config.utils import get_app_instance
from django.contrib.sites.models import Site
from django.contrib.syndication.views import Feed
from django.core.urlresolvers import reverse
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext as _, get_language_from_request

from djangocms_blog.settings import get_setting
from djangocms_blog.views import PostDetailView
from .models import Post


class LatestEntriesFeed(Feed):
    feed_type = Rss201rev2Feed

    def __call__(self, request, *args, **kwargs):
        self.request = request
        self.namespace, self.config = get_app_instance(request)
        return super(LatestEntriesFeed, self).__call__(request, *args, **kwargs)

    def link(self):
        return reverse('%s:posts-latest' % self.namespace, current_app=self.namespace)

    def title(self):
        return _('Blog articles on %(site_name)s') % {'site_name': Site.objects.get_current().name}

    def items(self, obj=None):
        return Post.objects.namespace(self.namespace).published().order_by('-date_published')[:10]

    def item_title(self, item):
        return item.safe_translation_getter('title')

    def item_description(self, item):
        if item.app_config.use_abstract:
            return item.safe_translation_getter('abstract')
        return item.safe_translation_getter('post_text')


class TagFeed(LatestEntriesFeed):

    def get_object(self, request, tag):
        return tag  # pragma: no cover

    def items(self, obj=None):
        return Post.objects.published().filter(tags__slug=obj)[:10]


class FBInstantFeed(Rss201rev2Feed):

    def rss_attributes(self):
        return {
            'version': self._version,
            'xmlns:content': 'http://purl.org/rss/1.0/modules/content/'
        }

    def add_root_elements(self, handler):
        handler.addQuickElement("title", self.feed['title'])
        handler.addQuickElement("link", self.feed['link'])
        handler.addQuickElement("description", self.feed['description'])
        if self.feed['language'] is not None:
            handler.addQuickElement("language", self.feed['language'])
        for cat in self.feed['categories']:
            handler.addQuickElement("category", cat)
        if self.feed['feed_copyright'] is not None:
            handler.addQuickElement("copyright", self.feed['feed_copyright'])
        handler.addQuickElement("lastBuildDate", rfc2822_date(self.latest_post_date()))
        if self.feed['ttl'] is not None:
            handler.addQuickElement("ttl", self.feed['ttl'])

    def add_item_elements(self, handler, item):
        super(FBInstantFeed, self).add_item_elements(handler, item)
        handler.startElement('content:encoded', {})
        handler._write('<![CDATA[')
        handler._write(force_text(item['content']))
        handler._write(']]>')
        handler.endElement('content:encoded')


class FBInstantArticles(LatestEntriesFeed):
    feed_type = FBInstantFeed

    def item_extra_kwargs(self, item):
        if not item:
            return {}
        language = get_language_from_request(self.request, check_path=True)
        key = item.get_cache_key(language, 'feed')
        content = cache.get(key)
        if not content:
            view = PostDetailView.as_view(instant_article=True)
            response = view(self.request, slug=item.safe_translation_getter('slug'))
            response.render()
            content = mark_safe(response.content)
            cache.set(key, content, timeout=get_setting('FEED_CACHE_TIMEOUT'))
        return {
            'content': content,
            'slug': item.safe_translation_getter('slug'),
        }
