// Snippet 10: lambda assigned in a statement at namespace scope: there is no
// enclosing named function, so the result must be empty (no bogus name).
namespace {
const char* kStage = "init";

auto report_error = [](const char* msg) {
    // @expect-func: (none)
    PROF_ERROR("callback failed: %s", msg);
};
}  // namespace
