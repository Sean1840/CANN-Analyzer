void ProfilingAgent::ReportProfApi(const uint32_t devId, RuntimeProfApiData& profApiData) const
{
    const int32_t ret = MsprofReportApi(true, &apiInfo);
    if (ret != MSPROF_ERROR_NONE) {
        RT_LOG_CALL_MSG(ERR_MODULE_PROFILE, "Failed to report profiling API data, devId=%u, ret=%d.", devId, ret);
        return;
    }
}
