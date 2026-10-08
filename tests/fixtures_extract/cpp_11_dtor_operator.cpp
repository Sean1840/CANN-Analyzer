// Snippet 11: destructor and symbolic operator definitions.
class Buffer {
public:
    ~Buffer();
    bool operator==(const Buffer& other) const;
private:
    size_t size_;
};

Buffer::~Buffer()
{
    // @expect-func: Buffer::~Buffer
    DRV_INFO("buffer released, size=%zu", size_);
}

bool Buffer::operator==(const Buffer& other) const
{
    // @expect-func: Buffer::operator==
    DRV_INFO("compare buffers %p %p", static_cast<const void*>(this), static_cast<const void*>(&other));
    return size_ == other.size_;
}
