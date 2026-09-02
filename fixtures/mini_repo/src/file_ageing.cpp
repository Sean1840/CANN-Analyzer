#include "msprof_dlog.h"

int32_t FileAgeing::Init2()
{
    unsigned long long availableVolume = 0;
    if (availableVolume < STORAGE_RESERVED_VOLUME) {
        MSPROF_LOGE(
            "Available volume:%" PRIu64 " (%lluMB) less than 20MB. Data will not be collected.", availableVolume,
            (availableVolume >> MOVE_BIT));
        return PROFILING_FAILED;
    }
    return PROFILING_SUCCESS;
}
