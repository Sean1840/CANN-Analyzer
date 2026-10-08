// Snippet 07: namespaced function with a switch statement inside.
namespace cann {
namespace runtime {

void ConfigureMode(int mode)
{
    switch (mode) {
        case 0:
            // @expect-func: ConfigureMode
            RT_LOG_INFO("mode 0 selected");
            break;
        default:
            // @expect-func: ConfigureMode
            RT_LOG_ERROR("unsupported mode=%d", mode);
            break;
    }
}

}  // namespace runtime
}  // namespace cann
