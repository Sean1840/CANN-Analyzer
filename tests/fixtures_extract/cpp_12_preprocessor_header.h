// Snippet 12: header with function-like logging macros and an inline function.
#ifndef CANN_LOG_INNER_H
#define CANN_LOG_INNER_H

#define LOG_IF_FAIL(cond, fmt, ...)          \
    do {                                     \
        if (!(cond)) {                       \
            MSPROF_LOGE(fmt, ##__VA_ARGS__); \
        }                                    \
    } while (0)

inline bool IsLogEnabled(int level)
{
    if (level < 0) {
        // @expect-func: IsLogEnabled
        MSPROF_LOGW("invalid log level=%d", level);
        return false;
    }
    return true;
}

#endif
