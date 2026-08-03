from open_webui.utils.middleware import get_response_error_content, normalize_form_files


def test_provider_error_message_is_preferred_over_raw_mapping():
    response_data = {
        'error': {
            'message': 'Function call is missing a thought_signature.',
            'type': 'invalid_request_error',
        }
    }

    assert (
        get_response_error_content(response_data)
        == 'Function call is missing a thought_signature.'
    )


def test_provider_error_detail_remains_supported():
    assert get_response_error_content({'error': {'detail': 'provider failed'}}) == 'provider failed'


def test_success_response_has_no_error():
    assert get_response_error_content({'choices': []}) is None


def test_legacy_web_search_source_normalizes_null_files():
    form_data = {'files': None}
    files = normalize_form_files(form_data)
    files.append({'type': 'web_search'})

    assert form_data['files'] == [{'type': 'web_search'}]
