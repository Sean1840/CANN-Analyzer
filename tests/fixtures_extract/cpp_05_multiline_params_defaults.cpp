// Snippet 05: multi-line parameter list with brace default arguments and a
// K&R style opening brace.
static int Configure(
    const Options& options = Options{},
    const std::string& name = "default",
    int flags = 0)
{
    // @expect-func: Configure
    GELOGE("configure failed for %s, flags=%d", name.c_str(), flags);
    return 0;
}
