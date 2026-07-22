import os
import sys
import json
import logging
from pathlib import Path
from typing import Optional

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, HTMLResponse
from pydantic import BaseModel
from openai import OpenAI

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 支持 PyInstaller 打包后的路径查找
if getattr(sys, 'frozen', False):
    BASE_DIR = Path(sys._MEIPASS)
else:
    BASE_DIR = Path(__file__).parent

app = FastAPI(
    title="兆辉防腐科技 · 文章运营助手",
    description="智能多平台文章生成工具",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── 平台规则定义 ────────────────────────────────────────
PLATFORM_RULES = {
    "baijiahao": {
        "name": "百家号",
        "rules": "百家号平台规则与风格指南：\n"
                 "1. 标题要求：吸引眼球、制造悬念或共鸣，15-30字为佳，善用数字和疑问句式\n"
                 "2. 开头要求：前100字必须有黄金钩子，用场景带入或痛点切入，快速抓住读者\n"
                 "3. 段落要求：每段不超过3-4行，多用短句，一段话只讲一个核心点\n"
                 "4. 语言风格：接地气但不失专业，多用设问和排比增强节奏感\n"
                 "5. 排版要求：适当使用小标题、分隔线（---）、emoji点缀\n"
                 "6. SEO要求：自然融入长尾关键词，提高搜索推荐权重\n"
                 "7. 结尾要求：引导互动（点赞、评论、转发），可设开放性问题\n"
                 "8. 配图建议：建议每800-1000字配一张图，图文穿插",
        "style": "通俗易懂、节奏明快、有情绪张力"
    },
    "wechat": {
        "name": "微信公众号",
        "rules": "微信公众号平台规则与风格指南：\n"
                 "1. 标题要求：信息明确且专业，避免过于夸张的标题党，12-20字为佳\n"
                 "2. 开头要求：开门见山，说明文章价值和阅读回报，建立专业信任感\n"
                 "3. 正文要求：结构清晰，层次分明，多用二级标题分隔不同模块\n"
                 "4. 语言风格：专业但不晦涩，措辞严谨，适当使用行业术语但需解释\n"
                 "5. 排版要求：正文14-16px字，行间距1.75倍，段间距明显\n"
                 "6. 深度要求：内容要有深度，提供干货价值，一篇文章讲透一个主题\n"
                 "7. 结尾要求：总结核心观点，引导关注或转发\n"
                 "8. 配图建议：首图需精良，正文中配合示意图、表格等增强说服力",
        "style": "专业深度、结构清晰、有价值密度"
    },
    "website": {
        "name": "官方网站",
        "rules": "官方网站发布内容规则与风格指南：\n"
                 "1. 标题要求：准确、正式、专业，直接反映文章主题，便于搜索引擎索引\n"
                 "2. 开头要求：专业概述，交代背景和文章目的，体现企业专业形象\n"
                 "3. 正文要求：详实、严谨、数据支撑，多维度展开主题\n"
                 "4. 语言风格：正式、客观、权威，适当使用专业术语，展示技术实力\n"
                 "5. 排版要求：规范层级标题，使用列表、表格、示意图等丰富呈现形式\n"
                 "6. 权威性要求：引用标准规范（如HG/T、GB/T等），增强可信度\n"
                 "7. 结尾要求：可附带公司简介、联系方式或相关产品链接（隐式引导）\n"
                 "8. 配图建议：产品实拍图、工艺流程图、案例实景照片等",
        "style": "权威专业、技术扎实、企业级表达"
    },
    "sina": {
        "name": "新浪（新闻稿）",
        "rules": "新浪新闻/新闻稿发布规则与风格指南：\n"
                 "1. 标题要求：新闻标题格式，简明扼要直击核心，15-20字为佳\n"
                 "2. 开头要求：倒金字塔结构，首段交代5W1H\n"
                 "3. 正文要求：事实优先，数据说话，层层递进，多角度呈现\n"
                 "4. 语言风格：客观中立、新闻语体，避免过度营销语\n"
                 "5. 排版要求：段落短小精悍，每段不超过5行，层次分明\n"
                 "6. 新闻要素：包含行业背景、技术亮点、市场意义等新闻价值点\n"
                 "7. 结尾要求：展望前景或行业影响，自然收束\n"
                 "8. 配图建议：活动现场图、产品图或数据图表",
        "style": "客观新闻、事实驱动、行业视野"
    },
}

# ── 写作角度定义 ────────────────────────────────────────
WRITING_ANGLES = {
    "professional": {
        "name": "专业科普",
        "prompt": "以专业科普的角度写作，用通俗易懂的语言解释专业技术原理和应用，兼顾专业深度和可读性"
    },
    "technical": {
        "name": "技术解析",
        "prompt": "以技术深度分析的角度写作，展开技术细节、工艺参数、标准规范、性能对比等，展现技术权威性"
    },
    "industry": {
        "name": "行业资讯",
        "prompt": "以行业新闻报道的角度写作，结合行业动态、市场趋势、政策法规等，体现行业视野"
    },
    "case": {
        "name": "案例分享",
        "prompt": "以案例分享的角度写作，通过实际工程案例进行讲述，包含客户需求、技术方案、实施效果等"
    },
    "light": {
        "name": "轻松科普",
        "prompt": "以轻松有趣的角度写作，用类比、故事、比喻等方式让专业内容变得有趣易懂，适合非专业读者"
    },
}

# ── 请求模型 ────────────────────────────────────────────
class GenerateRequest(BaseModel):
    topic: str
    platform: str
    angle: str
    length: str = "medium"
    additional_notes: Optional[str] = None
    # 前端传入的 API 配置（可选，优先级高于 .env）
    api_key: Optional[str] = None
    api_base: Optional[str] = None
    model: Optional[str] = None


LENGTH_CONFIG = {
    "short": {"desc": "1500-2000字", "system_hint": "精炼有力，核心要点突出，控制在1500-2000字"},
    "medium": {"desc": "2000-3500字", "system_hint": "全面展开主题，充实的专业内容，控制在2000-3500字"},
    "long": {"desc": "3500-5000字", "system_hint": "深度详实，全方位剖析主题，控制在3500-5000字"},
}


# ── 公司背景信息 ────────────────────────────────────────
COMPANY_CONTEXT = """公司简介：江苏兆辉防腐科技有限公司，位于江苏省，专业从事防腐设备制造与工程服务。

核心技术领域：
1. 板衬四氟（PTFE板衬）工艺：采用优质聚四氟乙烯板材，通过热熔焊接、负压成型等工艺，在钢制设备内壁衬覆致密PTFE防腐层，适用于强酸、强碱、高温、高纯等苛刻工况。
2. 内衬PE（聚乙烯）工艺：采用滚塑或板材焊接工艺，在设备内壁衬覆聚乙烯防腐层，耐腐蚀、抗冲击、无毒无味，广泛应用于化工储运、环保等领域。
3. 内衬PO（聚烯烃）工艺：采用滚塑成型工艺，衬层厚度均匀、整体性优异，耐腐蚀性能优越，性价比高。
4. 防腐设备制造：各类防腐储罐、反应釜、塔器、管道及管件的设计、制造与安装。

主营产品：钢衬四氟储罐、钢衬PE储罐、钢衬PO储罐、四氟衬里反应釜、防腐塔器、防腐管道及管件、板衬四氟设备等。

应用领域：化工、石油、制药、冶金、环保、电子、食品等行业的防腐工程。

资质与技术：拥有多项防腐技术专利，严格按HG/T 20536、GB/T 26501等标准执行生产，产品通过多项质量认证。"""


# ── 生成系统提示词 ─────────────────────────────────────
def build_system_prompt(platform: str, angle: str, length_key: str) -> str:
    p_info = PLATFORM_RULES[platform]
    a_info = WRITING_ANGLES[angle]
    l_info = LENGTH_CONFIG[length_key]

    return f"""你是一位专业的工业防腐技术文章撰稿人，擅长撰写高质量的化工防腐设备相关文章。

{COMPANY_CONTEXT}

## 当前任务
请根据用户指定的主题，按照以下要求撰写文章：

### 写作角度
{a_info["prompt"]}

### 目标平台
平台：{p_info["name"]}
平台规则与风格：
{p_info["rules"]}
平台语言风格：{p_info["style"]}

### 篇幅要求
{l_info["system_hint"]}

### 通用要求
1. 文章必须包含明确的标题（开头一行 ## 标题）
2. 内容要专业有深度，体现江苏兆辉防腐科技的技术实力
3. 适当融入行业背景、技术原理、应用场景等专业内容
4. 全文保持逻辑连贯，层层递进
5. 技术数据、标准引用尽可能具体准确
6. 根据平台规则调整语气、排版和互动方式
7. 不要直接硬广推销，而是通过专业内容建立信任
8. 正文中不要重复公司全称作为段落开头
9. 全文用中文撰写"""


# ── 流式生成 ────────────────────────────────────────────
def stream_from_openai(api_key: str, base_url: str, model: str, messages: list):
    http_client = httpx.Client(timeout=httpx.Timeout(120.0, connect=30.0))
    try:
        client = OpenAI(api_key=api_key, base_url=base_url, http_client=http_client)
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.7,
            max_tokens=8192,
            stream=True,
        )
        for chunk in response:
            delta = chunk.choices[0].delta if chunk.choices else None
            if delta and delta.content:
                yield f"data: {json.dumps({'text': delta.content})}\n\n"
        yield "data: [DONE]\n\n"
    except Exception as e:
        logger.error(f"生成失败: {e}", exc_info=True)
        err_msg = str(e)
        if "401" in err_msg or "Incorrect API key" in err_msg:
            err_msg = "API Key 无效，请检查输入的 API Key 是否正确"
        elif "timeout" in err_msg.lower() or "timed out" in err_msg.lower():
            err_msg = "请求超时，请检查 API 地址和网络连接"
        elif "connect" in err_msg.lower() or "connection" in err_msg.lower():
            err_msg = "无法连接到 API 服务，请检查 API 地址是否正确，或更换其他 API 提供商"
        elif "429" in err_msg:
            err_msg = "API 请求频率过高，请稍后重试"
        elif "model" in err_msg.lower() and "not" in err_msg.lower():
            err_msg = f"模型 '{model}' 不可用，请检查模型名称是否正确"
        yield f"data: {json.dumps({'error': err_msg})}\n\n"
        yield "data: [DONE]\n\n"
    finally:
        http_client.close()


# ── API 路由 ────────────────────────────────────────────
@app.get("/api/platforms")
def get_platforms():
    return {
        k: {"name": v["name"], "rules": v["rules"], "style": v["style"]}
        for k, v in PLATFORM_RULES.items()
    }


@app.get("/api/angles")
def get_angles():
    return {k: {"name": v["name"]} for k, v in WRITING_ANGLES.items()}


@app.get("/api/lengths")
def get_lengths():
    return {k: {"desc": v["desc"]} for k, v in LENGTH_CONFIG.items()}


@app.post("/api/generate")
async def generate_article(req: GenerateRequest):
    if req.platform not in PLATFORM_RULES:
        raise HTTPException(400, f"不支持的平台: {req.platform}")
    if req.angle not in WRITING_ANGLES:
        raise HTTPException(400, f"不支持的写作角度: {req.angle}")

    # 优先使用前端传入的配置，否则回退到 .env
    api_key = req.api_key or os.getenv("OPENAI_API_KEY", "")
    api_base = (req.api_base or os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")).rstrip("/")
    model = req.model or os.getenv("OPENAI_MODEL", "gpt-4o")

    if not api_key or api_key == "sk-your-api-key-here":
        async def error_stream():
            yield f"data: {json.dumps({'error': '请先在右上角 ⚙ 设置中填写 API Key'})}\n\n"
            yield "data: [DONE]\n\n"
        return StreamingResponse(error_stream(), media_type="text/event-stream")

    system_prompt = build_system_prompt(req.platform, req.angle, req.length)
    user_prompt = f"请围绕以下主题撰写文章：\n{req.topic}"
    if req.additional_notes:
        user_prompt += f"\n\n额外要求：\n{req.additional_notes}"

    logger.info(f"生成文章: platform={req.platform}, angle={req.angle}, length={req.length}, topic={req.topic}")

    sync_gen = stream_from_openai(api_key, api_base, model, [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ])

    async def async_iter():
        for item in sync_gen:
            yield item

    return StreamingResponse(async_iter(), media_type="text/event-stream")


# ── 静态文件服务 ────────────────────────────────────────
@app.get("/")
async def serve_index():
    index_path = BASE_DIR / "index.html"
    if not index_path.exists():
        return HTMLResponse("<h1>文章运营助手</h1><p>请先部署前端页面。</p>")
    return HTMLResponse(index_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8350, reload=True)
