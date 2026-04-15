/**
 * Frontend Logger Utility
 */
class Logger {
    constructor() {
        this.isDevelopment = import.meta.env.DEV;
    }

    formatMessage(level, message, ...args) {
        const timestamp = new Date().toISOString();
        return [`[${timestamp}] [${level}]`, message, ...args];
    }

    info(message, ...args) {
        if (this.isDevelopment) {
            console.log(...this.formatMessage(`INFO`, message), ...args);
        }
    }

    warn(message, ...args) {
        console.warn(...this.formatMessage('WARN', message), ...args);
    }

    error(message, ...args) {
        console.error(...this.formatMessage('ERROR', message), ...args);
    }

    debug(message, ...args) {
        if (this.isDevelopment) {
            console.debug(...this.formatMessage('DEBUG', message), ...args);
        }
    }

    chat(message, ...args) {
        if (this.isDevelopment) {
            console.log(...this.formatMessage('CHAT', message), ...args);
        }
    }
}

export default new Logger();
