Docker 镜像内编译好的二进制文件，构建时使用 -fsanitize=address,undefined。Find 代理在容器内用构造的输入通过 Bash 运行此二进制。发生内存错误时，ASAN 向 stderr 写入详细错误报告，包含崩溃类型、调用栈和内存地址。该文本是主要的发现信号。
