// Snippet 06: K&R brace plus a for body (the classic msprof file-ageing shape).
int32_t FileAgeing::Init2()
{
    unsigned long long availableVolume = 0;
    for (int i = 0; i < kRetry; ++i) {
        // @expect-func: FileAgeing::Init2
        MSPROF_LOGE("available volume:%llu less than 20MB, data will not be collected", availableVolume);
        return PROFILING_FAILED;
    }
    // @expect-func: FileAgeing::Init2
    MSPROF_LOGI("file ageing init ok, volume=%llu", availableVolume);
    return PROFILING_SUCCESS;
}
