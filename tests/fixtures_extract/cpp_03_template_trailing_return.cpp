// Snippet 03: template function with a trailing return type.
template <typename T>
auto GatherValues(const std::vector<T>& input) -> std::vector<T> {
    // @expect-func: GatherValues
    RT_LOG_DEBUG("gather values, size=%zu", input.size());
    return input;
}
