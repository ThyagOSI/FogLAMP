#ifndef _PLUGIN_API
#define _PLUGIN_API
 
typedef struct {
        const char	*name;
        const char	*version;
        unsigned int	options;
        const char	*type;
        const char	*interface;
} PLUGIN_INFORMATION;
 
typedef struct {
        char         *message;
        char         *entryPoint;
        bool         retryable;
} PLUGIN_ERROR;
 
typedef void * PLUGIN_HANDLE;
 
/**
 * Plugin options bitmask values
 */
#define SP_COMMON       0x0001
#define SP_READINGS     0x0002
 
/**
 * Plugin types
 */
#define PLUGIN_TYPE_STORAGE     "storage"
#endif