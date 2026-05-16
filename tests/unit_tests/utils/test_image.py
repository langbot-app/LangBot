from langbot.pkg.utils.image import get_qq_image_downloadable_url


def test_get_qq_image_downloadable_url_preserves_https_scheme():
    url, query = get_qq_image_downloadable_url('https://gchat.qpic.cn/gchatpic_new/abc/0?term=2&is_origin=1')

    assert url == 'https://gchat.qpic.cn/gchatpic_new/abc/0'
    assert query == {'term': ['2'], 'is_origin': ['1']}


def test_get_qq_image_downloadable_url_preserves_http_scheme():
    url, query = get_qq_image_downloadable_url('http://gchat.qpic.cn/gchatpic_new/abc/0?term=2')

    assert url == 'http://gchat.qpic.cn/gchatpic_new/abc/0'
    assert query == {'term': ['2']}


def test_get_qq_image_downloadable_url_defaults_missing_scheme_to_http():
    url, query = get_qq_image_downloadable_url('gchat.qpic.cn/gchatpic_new/abc/0?term=2')

    assert url == 'http://gchat.qpic.cn/gchatpic_new/abc/0'
    assert query == {'term': ['2']}
