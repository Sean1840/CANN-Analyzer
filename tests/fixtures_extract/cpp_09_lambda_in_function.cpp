// Snippet 09: lambda passed to a call inside a named function.
void SortItems(std::vector<Item>& items)
{
    // @expect-func: SortItems
    RT_LOG_INFO("sorting %zu items", items.size());
    std::sort(items.begin(), items.end(), [](const Item& lhs, const Item& rhs) {
        // @expect-func: SortItems
        RT_LOG_WARNING("comparing %d and %d", lhs.id, rhs.id);
        return lhs.id < rhs.id;
    });
}
