


class StudyRAGError(Exception):
    pass


class PDFError(StudyRAGError):
    pass


class DocumentoError(StudyRAGError):
    pass


class LLMError(StudyRAGError):
    pass
