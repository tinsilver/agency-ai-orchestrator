class RequestCategory:
    """Valid request categories for client requests."""

    BLOG_POST = "blog_post"
    SEO_OPTIMIZATION = "seo_optimization"
    BUG_FIX = "bug_fix"
    CONTENT_UPDATE = "content_update"
    BUSINESS_INFO_UPDATE = "business_info_update"
    NEW_PAGE = "new_page"
    FORM_CHANGES = "form_changes"
    DESIGN_CHANGES = "design_changes"
    FEATURE_REQUEST = "feature_request"
    UNCLEAR = "unclear"

    ALL = [
        BLOG_POST,
        SEO_OPTIMIZATION,
        BUG_FIX,
        CONTENT_UPDATE,
        BUSINESS_INFO_UPDATE,
        NEW_PAGE,
        FORM_CHANGES,
        DESIGN_CHANGES,
        FEATURE_REQUEST,
        UNCLEAR,
    ]
