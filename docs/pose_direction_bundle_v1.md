# 姿态口播与简笔包 v1

`pose-direction-bundle` schema version `1` 是一份生产者文件。一条记录对应一张参考照片，里面只有两样产品：摄影师可以对着模特说的一句口播，以及用本地关键点画出的一张简笔图。

这不是 Photo Intelligence Bundle v1。App 集成合同仍然是那份 release bundle。这也不是 PKB1 合成夹具。`authority` 为 false。它不是 T14 golden，也不表示生产解锁。手机 App 的点按画面还没有做。

构建函数只接受内存里的记录。稳定 id 用已有的哈希形式，例如 `img-04-aabebf45`，不写原文件名、路径、照片字节或 EXIF。简笔可以是 SVG 正文，也可以是包内相对的 `svg` 文件名。构图、光线、目光、服装这四项短说明只有在上游已经给出时才写入。缺一句口播，或简笔里没有画出的身体，函数直接失败，不补一条。
