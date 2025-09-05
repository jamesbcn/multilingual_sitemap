from odoo import models

class Website(models.Model):
    _inherit = 'website'

    def _enumerate_pages(self, query_string=None, force=False):
        """Generate sitemap URLs for pages + blogs, with logging for debugging."""
        from datetime import datetime
        from odoo import fields
        import logging

        _logger = logging.getLogger(__name__)
        url_set = set()
        active_languages = self.language_ids.filtered("active")
        default_lang = self.default_lang_id.code if self.default_lang_id else "en_US"

        # Get current website
        website = self.env['website'].get_current_website()
        _logger.info("Current website: %s", website)

        # -----------------------
        # Helper functions
        # -----------------------
        def _prefix_url(lang, url):
            if not isinstance(url, str):
                return None
            if lang.code == default_lang:
                return url
            if lang.code.startswith("es"):
                return "/es" + url if url != "/" else "/es"
            return "/" + lang.code + url if url != "/" else "/" + lang.code

        def _yield_url(url, extra=None):
            if not url or url in url_set:
                return
            url_set.add(url)
            record = {"loc": url}
            if extra:
                record.update(extra)
            _logger.info("Yielding URL: %s", url)
            yield record

        # -----------------------
        # Website Pages
        # -----------------------
        domain = [("url", "!=", "/")]
        if not force:
            domain += [
                ("website_indexed", "=", True),
                ("website_published", "=", True),
                "|",
                ("date_publish", "=", False),
                ("date_publish", "<=", fields.Datetime.now()),
            ]
        if query_string:
            domain += [("url", "like", query_string)]

        pages = self._get_website_pages(domain)
        _logger.info("Found %d pages", len(pages))

        for page in pages:
            for lang in active_languages:
                url = _prefix_url(lang, page["url"])
                _logger.info("Page %s (lang=%s) URL: %s", page['name'], lang.code, url)
                last_updated_date = max(
                    [d for d in (page.write_date, page.view_id.write_date) if isinstance(d, datetime)],
                    default=None,
                )
                extra = {}
                if page.view_id and page.view_id.priority != 16:
                    extra["priority"] = min(round(page.view_id.priority / 32.0, 1), 1)
                if last_updated_date:
                    extra["lastmod"] = last_updated_date.date()
                yield from _yield_url(url, extra)

        # -----------------------
        # Blog posts
        # -----------------------
        current_datetime = fields.Datetime.now()
        blog_posts = self.env['blog.post'].search([
            ('website_published', '=', True),
            ('website_id', 'in', (website.id, False)),
            '|',
            ('post_date', '=', False),
            ('post_date', '<=', current_datetime)
        ])
        _logger.info("Found %d published blog posts with valid dates", len(blog_posts))

        for post in blog_posts:
            _logger.info("Processing blog post ID=%s title=%s post_date=%s", post.id, post.name, post.post_date)
            for lang in active_languages:
                try:
                    post_lang = post.with_context(lang=lang.code, website_id=website.id)
                    url = getattr(post_lang, 'website_url', None)
                    if not url:
                        _logger.warning("No website_url for post ID=%s lang=%s", post.id, lang.code)
                        continue
                    if website.domain and url.startswith(website.domain):
                        url = url.replace(website.domain, "")
                    lang_url = _prefix_url(lang, url)
                    _logger.info("Blog post ID=%s lang=%s URL=%s", post.id, lang.code, lang_url)
                    yield from _yield_url(lang_url)
                except Exception as e:
                    _logger.exception("Error generating URL for post ID=%s lang=%s: %s", post.id, lang.code, e)