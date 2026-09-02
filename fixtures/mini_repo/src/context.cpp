#include "log_inner.h"

aclError aclrtCreateContext(aclrtContext *context, int32_t deviceId) {
    if (context == nullptr) {
        ACL_LOG_ERROR("create context failed, flags=%u", 1u);
        return ACL_ERROR_INVALID_PARAM;
    }
    ACL_LOG_INFO("create context success, deviceId=%d", deviceId);
    ACL_LOG_EVENT("context created on device %d", deviceId);
    return ACL_ERROR_NONE;
}

void OnMallocFail(size_t n) {
    RT_LOG_ERROR("malloc failed, size=%zu", n);
}
