from open_webui.utils.payload import drop_empty_tools


def test_empty_tools_are_omitted_at_provider_boundary():
    payload = {'model': 'provider/model', 'messages': [], 'tools': []}

    assert drop_empty_tools(payload) == {
        'model': 'provider/model',
        'messages': [],
    }


def test_nonempty_tools_are_preserved():
    tools = [{'type': 'function', 'function': {'name': 'search'}}]
    payload = {'tools': tools}

    assert drop_empty_tools(payload) == {'tools': tools}
