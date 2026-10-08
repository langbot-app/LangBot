"""Crawler-visible preview for the hosted Cloud frontend only."""

CLOUD_IMAGE = 'https://cloud.langbot.app/social/cloud-v3.png'


def cloud_preview_html(html: str, hostname: str) -> str:
    if hostname.split(':', 1)[0].lower() != 'cloud.langbot.app':
        return html
    tags = (
        '<meta property="og:type" content="website">'
        '<meta property="og:title" content="LangBot Cloud">'
        '<meta property="og:description" content="Run LangBot in the cloud.">'
        f'<meta property="og:image" content="{CLOUD_IMAGE}">'
        '<meta property="og:image:width" content="1200">'
        '<meta property="og:image:height" content="630">'
        '<meta name="twitter:card" content="summary_large_image">'
        '<meta name="twitter:title" content="LangBot Cloud">'
        f'<meta name="twitter:image" content="{CLOUD_IMAGE}">'
    )
    return html.replace('</head>', tags + '</head>', 1)
