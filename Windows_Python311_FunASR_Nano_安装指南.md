# SmartSync ???????????Windows + Python 3.11 + FFmpeg + FunASR?

本文档用于在 Windows 环境下，为 `SmartSync` 项目安装本地化语音转写与发言人区分能力。

目标环境：
- 操作系统：Windows
- Python：`3.11`
- 音频工具：`FFmpeg`
- ASR 模型：`damo/speech_paraformer-large_asr_nat-zh-cn-16k-common-vocab8404-pytorch`
- 发言人区分：`CAM++ + Faiss`
- 项目路径：`D:\Desktop\AI会议\smartsync`

推荐原则：
- 不使用 `Python 3.13`
- 先用 `CPU` 跑通
- 跑通后再切换 `CUDA`

---

## 1. 硬件建议

你的机器信息：
- GPU：`NVIDIA GeForce RTX 4060`
- 显存：`8GB`
- 驱动：`566.24`
- CUDA Driver：`12.7`

结论：
- 这套环境适合运行本地转写
- `RTX 4060 8GB` 可以用于中小规模会议音频转写
- 推荐先使用 `CPU` 模式验证，再切到 `CUDA`

---

## 2. 安装 Python 3.11

请安装 `Python 3.11.x`。

安装时务必勾选：
- `Add Python to PATH`
- `pip`
- `venv`

安装完成后，在 PowerShell 验证：

```powershell
py -3.11 --version
```

期望输出示例：

```powershell
Python 3.11.x
```

---

## 3. 安装 FFmpeg

推荐方式一：使用 `winget`

```powershell
winget install Gyan.FFmpeg
```

安装完成后，重新打开 PowerShell，再执行：

```powershell
ffmpeg -version
```

如果能看到版本信息，说明安装成功。

### 手动安装方式

如果你不想用 `winget`：
- 下载 Windows 版 `FFmpeg`
- 解压到例如：`D:\tools\ffmpeg`
- 将 `D:\tools\ffmpeg\bin` 加入系统环境变量 `PATH`

然后再次验证：

```powershell
ffmpeg -version
```

---

## 4. 创建项目虚拟环境

进入后端目录：

```powershell
cd D:\Desktop\AI会议\smartsync\backend
```

创建虚拟环境：

```powershell
py -3.11 -m venv .venv
```

激活虚拟环境：

```powershell
.\.venv\Scripts\activate
```

---

## 5. 升级安装工具

```powershell
python -m pip install -U pip setuptools wheel
```

---

## 6. 安装 PyTorch

### 6.1 先安装 CPU 版，优先跑通

```powershell
pip install torch torchvision torchaudio
```

说明：
- 先用 CPU 版可以排除大部分环境问题
- 确认本地转写流程没问题后，再切换为 GPU 版

---

## 7. 安装项目依赖

```powershell
pip install -r requirements.txt
```

如果某个包失败，请先记录报错信息，不要整套重装。

---

## 8. 补装 FunASR 相关依赖

```powershell
pip install funasr modelscope faiss-cpu numpy
```

说明：
- `funasr`：语音识别框架
- `modelscope`：模型加载与下载
- `faiss-cpu`：说话人 embedding 聚类
- `numpy`：音频向量处理

---

## 9. 模型说明

当前项目需要的不是单一模型，而是一组模型：

### 9.1 语音识别模型
- `damo/speech_paraformer-large_asr_nat-zh-cn-16k-common-vocab8404-pytorch`

### 9.2 VAD 模型
- `damo/speech_fsmn_vad_zh-cn-16k-common-pytorch`

### 9.3 标点恢复模型
- `damo/punc_ct-transformer_cn-en-common-vocab471067-large`

### 9.4 发言人 embedding 模型
- `iic/speech_campplus_sv_zh-cn_16k-common`

说明：
- ???????? `Paraformer` ??????
- 发言人区分仍然依赖 `CAM++` 提取说话人向量，再由 `Faiss` 聚类

---

## 10. 配置 `backend/.env`

在目录 `D:\Desktop\AI会议\smartsync\backend` 下创建文件：

- `D:\Desktop\AI会议\smartsync\backend\.env`

写入以下最小配置：

```env
ASR_PROVIDER=local
FUNASR_MODEL_DIR=D:/Desktop/AI会议/smartsync/models/funasr

FUNASR_DEVICE=cpu
FUNASR_NGPU=0
FUNASR_DISABLE_UPDATE=true
FUNASR_HUB=ms

FUNASR_ASR_MODEL=damo/speech_paraformer-large_asr_nat-zh-cn-16k-common-vocab8404-pytorch
FUNASR_VAD_MODEL=damo/speech_fsmn_vad_zh-cn-16k-common-pytorch
FUNASR_PUNC_MODEL=damo/punc_ct-transformer_cn-en-common-vocab471067-large
FUNASR_CAMPP_MODEL=iic/speech_campplus_sv_zh-cn_16k-common

FUNASR_SAMPLE_RATE=16000
FUNASR_BATCH_SIZE_S=300
FUNASR_MIN_SEGMENT_MS=800
FUNASR_MERGE_GAP_MS=1200
FUNASR_MAX_SPEAKERS=8
FUNASR_SPEAKER_SIMILARITY_THRESHOLD=0.72
```

说明：
- `ASR_PROVIDER=local` 表示走本地转写链路
- `FUNASR_MODEL_DIR` 表示模型缓存和离线模型统一存放目录
- `FUNASR_DEVICE=cpu` 表示先用 CPU 验证
- 等 CPU 跑通后，再改成 `cuda`

---

## 11. 当前项目默认模型目录

现在项目已改为默认把模型缓存到项目目录下：

```text
D:\Desktop\AI会议\smartsync\models\funasr
```

推荐结构：

```text
D:\Desktop\AI会议\smartsync\models\funasr\
  ?? models\
      ?? damo\
      ?   ?? speech_paraformer-large_asr_nat-zh-cn-16k-common-vocab8404-pytorch\
      ?   ?? speech_fsmn_vad_zh-cn-16k-common-pytorch\
      ?   ?? punc_ct-transformer_cn-en-common-vocab471067-large\
      ?? iic\
          ?? speech_campplus_sv_zh-cn_16k-common\
- 联网时首次自动下载，会下载到这个目录
- 离线时，也可以把模型预先拷贝到这个目录

---

## 12. 启动后端

```powershell
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

---

## 13. 首次模型下载与测试

建议先上传一段较短音频测试：
- 时长：`10~30 秒`
- 格式：`wav`、`mp3`、`m4a`
- 内容：中文会议片段优先

首次转写时，系统会尝试下载：
- `damo/speech_paraformer-large_asr_nat-zh-cn-16k-common-vocab8404-pytorch`
- `damo/speech_fsmn_vad_zh-cn-16k-common-pytorch`
- `damo/punc_ct-transformer_cn-en-common-vocab471067-large`
- `iic/speech_campplus_sv_zh-cn_16k-common`

---

## 14. 基础检查命令

### 14.1 检查 FFmpeg

```powershell
ffmpeg -version
```

### 14.2 检查 Python 版本

```powershell
python --version
```

### 14.3 检查 FunASR 是否可导入

```powershell
python -c "import funasr; print('funasr ok')"
```

### 14.4 检查 Faiss 是否可导入

```powershell
python -c "import faiss; print('faiss ok')"
```

---

## 15. 跑通后切换 GPU

你的显卡是：
- `RTX 4060 8GB`

建议流程：
- 先 CPU 跑通
- 再改用 GPU

### 15.1 卸载 CPU 版 torch

```powershell
pip uninstall -y torch torchvision torchaudio
```

### 15.2 安装 CUDA 版 torch

通常可以安装官方提供的 `cu121` 版本：

```powershell
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
```

### 15.3 验证 CUDA

```powershell
python -c "import torch; print(torch.cuda.is_available()); print(torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'no cuda')"
```

### 15.4 修改 `.env`

将：

```env
FUNASR_DEVICE=cpu
FUNASR_NGPU=0
```

改成：

```env
FUNASR_DEVICE=cuda
FUNASR_NGPU=1
```

对 `8GB` 显存，建议同时把：

```env
FUNASR_BATCH_SIZE_S=120
```

---

## 16. 联网机下载模型脚本

项目已提供脚本：

- `backend/scripts/download_funasr_models.py`

使用方法：

```powershell
cd D:\Desktop\AI会议\smartsync\backend
.\.venv\Scripts\activate
python scripts\download_funasr_models.py
```

脚本会把模型下载到：

```text
D:\Desktop\AI会议\smartsync\models\funasr
```

---

## 17. 离线环境推荐 `.env`

如果你已经把模型下载到项目目录，建议改成本地路径：

```env
ASR_PROVIDER=local
FUNASR_MODEL_DIR=D:/Desktop/AI会议/smartsync/models/funasr

FUNASR_DEVICE=cpu
FUNASR_NGPU=0
FUNASR_DISABLE_UPDATE=true
FUNASR_HUB=ms

FUNASR_ASR_MODEL=D:/Desktop/AI??/smartsync/models/funasr/models/damo/speech_paraformer-large_asr_nat-zh-cn-16k-common-vocab8404-pytorch
FUNASR_VAD_MODEL=D:/Desktop/AI??/smartsync/models/funasr/models/damo/speech_fsmn_vad_zh-cn-16k-common-pytorch
FUNASR_PUNC_MODEL=D:/Desktop/AI??/smartsync/models/funasr/models/damo/punc_ct-transformer_cn-en-common-vocab471067-large
FUNASR_CAMPP_MODEL=D:/Desktop/AI??/smartsync/models/funasr/models/iic/speech_campplus_sv_zh-cn_16k-common
```

注意：实际下载后的目录名可能不是简短名字，而是带组织名或哈希目录。你需要以下载结果为准。

---

## 18. 常见问题

### 18.1 `editdistance` 编译失败

原因：
- 多数情况下是因为你使用了 `Python 3.13`

解决：
- 改用 `Python 3.11`

### 18.2 `ffmpeg was not found`

原因：
- 没装 `FFmpeg`
- 或者 `PATH` 没配置成功

### 18.3 `torch.cuda.is_available()` 为 `False`

原因：
- 安装的是 CPU 版 `torch`
- 或 CUDA 版 wheel 不匹配

### 18.4 模型下载失败，提示 `not registered`

原因：
- 使用了错误的短模型名

解决：
- 使用官方 repo id，例如 `damo/speech_paraformer-large_asr_nat-zh-cn-16k-common-vocab8404-pytorch`

---

## 19. 推荐操作顺序

1. 安装 `Python 3.11`
2. 安装 `FFmpeg`
3. 创建 `.venv`
4. 安装 CPU 版 `torch`
5. 安装项目依赖
6. 配置 `.env`
7. 启动后端
8. 上传短音频测试
9. 测试通过后再切换 `CUDA`

---

## 20. 当前项目相关文件

- `backend/app/config.py`
- `backend/app/services/local_asr.py`
- `backend/app/services/transcription.py`
- `backend/app/routers/upload.py`
- `backend/scripts/download_funasr_models.py`

