from open_webui.retrieval.utils import (
    DIRECT_TEXT_FULL_CONTEXT_MAX_BYTES,
    is_direct_text_attachment,
    is_full_context_item,
)


def direct_attachment(
    *,
    name='notes.md',
    content_type='text/markdown',
    size=81 * 1024,
    attachment_mode='auto',
):
    return {
        'type': 'file',
        'name': name,
        'size': size,
        'content_type': content_type,
        'attachment_mode': attachment_mode,
        'file': {
            'filename': name,
            'meta': {
                'size': size,
                'content_type': content_type,
                'data': {'attachment_mode': attachment_mode},
            },
        },
    }


def test_small_markdown_chat_attachment_uses_full_context():
    assert is_full_context_item(direct_attachment())


def test_text_detection_accepts_nested_upload_metadata():
    assert is_direct_text_attachment(
        filename='handoff.md',
        content_type='application/octet-stream',
        metadata={'data': {'attachment_mode': 'auto'}},
        size=81 * 1024,
    )


def test_knowledge_text_file_still_uses_rag():
    assert not is_full_context_item(direct_attachment(attachment_mode=None))


def test_pdf_attachment_still_uses_document_pipeline():
    assert not is_full_context_item(direct_attachment(name='document.pdf', content_type='application/pdf'))


def test_oversized_text_attachment_still_uses_rag():
    assert not is_full_context_item(direct_attachment(size=DIRECT_TEXT_FULL_CONTEXT_MAX_BYTES + 1))


def test_manual_full_context_remains_supported():
    assert is_full_context_item({'type': 'file', 'context': 'full'})
