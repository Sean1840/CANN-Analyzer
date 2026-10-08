// Snippet 04: qualified method with const / noexcept qualifiers and a site
// inside an if body.
class Worker {
public:
    void Run() noexcept;
private:
    bool started_;
    int ret_;
};

void Worker::Run() const noexcept {
    // @expect-func: Worker::Run
    MSPROF_LOGI("worker run started");
    if (!started_) {
        // @expect-func: Worker::Run
        MSPROF_LOGE("worker not started, ret=%d", ret_);
    }
}
