import os
import requests

# 读取环境变量
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_KEY")
SERVER_SENDKEY = os.getenv("SEND_KEY")
FETCH_URL = os.getenv("TARGET_URL")

# 浏览器UA伪装，防止被网站拦截
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
}

def fetch_web_content():
    """抓取目标网页文本"""
    try:
        resp = requests.get(FETCH_URL, headers=HEADERS, timeout=20)
        resp.raise_for_status()
        # 限制文本长度，避免大上下文消耗token
        return resp.text[:7000]
    except Exception as e:
        err_msg = f"网页抓取失败：{str(e)}"
        print(err_msg)
        return err_msg

def deepseek_extract_data(raw_text):
    """调用DeepSeek接口，提取结构化有效数据"""
    prompt = """
请严格按照要求处理下方网页内容：
1. 剔除导航、广告、底部版权、无用冗余信息；
2. 提取核心业务数据、资讯内容；
3. 排版清晰简洁，适合微信阅读；
4. 不要额外开场白、结束语，只输出整理后的内容。

网页原文：
""" + raw_text

    payload = {
        "model": "deepseek-chat",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2
    }
    api_headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }
    try:
        res = requests.post(
            "https://api.deepseek.com/v1/chat/completions",
            json=payload,
            headers=api_headers,
            timeout=35
        )
        json_data = res.json()
        return json_data["choices"][0]["message"]["content"]
    except Exception as e:
        err = f"DeepSeek接口调用异常：{str(e)}"
        print(err)
        return err

def send_wechat(title, content):
    """Server酱推送消息到个人微信"""
    if not SERVER_SENDKEY:
        return
    try:
        url = f"https://sctapi.ftqq.com/{SERVER_SENDKEY}.send"
        requests.post(
            url,
            data={"title": title, "desp": content},
            timeout=15
        )
    except Exception as e:
        print("微信推送失败：", str(e))

if __name__ == "__main__":
    print("===== 本轮定时任务开始 =====")
    page_content = fetch_web_content()
    result = deepseek_extract_data(page_content)
    send_wechat(title="定时AI数据抓取结果", content=result)
    print("任务执行完毕，消息已推送微信")
