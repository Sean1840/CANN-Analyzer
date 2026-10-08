// Snippet 01: constructor with a member initializer list and brace init.
class Session {
public:
    Session();
    void Reset();
private:
    int flags_;
    int retry_;
    void* handle_;
};

Session::Session() : flags_(1), retry_{3}, handle_(nullptr) {
    // @expect-func: Session::Session
    ACL_LOG_INFO("session created, flags=%d retry=%d", flags_, retry_);
}
