// Snippet 02: constructor with a multi-line parameter list and a multi-line
// initializer list.
Device::Device(
    const std::string& name,
    int device_id)
    : name_(name), device_id_(device_id) {
    // @expect-func: Device::Device
    ACL_LOG_INFO("device %s id=%d", name_.c_str(), device_id_);
}
