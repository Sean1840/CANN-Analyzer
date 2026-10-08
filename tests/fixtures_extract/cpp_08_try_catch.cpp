// Snippet 08: try / catch bodies.
void HandleFailure(const char* stage)
{
    try {
        // @expect-func: HandleFailure
        ACL_LOG_INFO("stage %s started", stage);
    } catch (const std::exception& e) {
        // @expect-func: HandleFailure
        ACL_LOG_ERROR("stage %s failed: %s", stage, e.what());
    }
}
