import os
import requests
import json
from datetime import datetime

# 环境变量
DEEPSEEK_KEY = os.getenv("DEEPSEEK_API_KEY")
SEND_KEY = os.getenv("SERVER_SENDKEY")
STATE_FILE = "signal_state.json"
# 单日交易提醒最大条数上限
DAILY_MAX_ALERT = 5

def load_signal_state():
    """加载状态：日期、推送计数、上一次信号类型"""
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    # 初始化默认状态
    return {
        "today_date": "",
        "alert_count": 0,
        "last_signal": "none"
    }

def save_signal_state(state):
    """写入状态文件"""
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

def reset_daily_state(today_str):
    """新一天到来，重置计数"""
    return {
        "today_date": today_str,
        "alert_count": 0,
        "last_signal": "none"
    }

# Server酱推送
def send_wechat(title: str, content: str):
    if not SEND_KEY:
        return
    try:
        url = f"https://sctapi.ftqq.com/{SEND_KEY}.send"
        requests.post(url, data={"title": title, "desp": content}, timeout=15)
        print(f"已推送微信 | {title}")
    except Exception as e:
        print(f"推送失败: {e}")

# 调用DeepSeek联网分析行情
def get_stock_analysis(current_time_str: str, is_close_summary: bool = False):
    system_prompt = """
你是港股短线交易分析师，专注腾讯控股(00700.HK)研判，必须联网获取实时行情数据：
可获取内容：实时股价、当日成交量、分时走势、K线、恒生指数、板块行情、公司新闻、资金流向、市场情绪。

两种工作模式：
1. 盘中5分钟巡检模式：
只输出三种结果之一：【买入信号】【卖出信号】【观望持有】
只有行情完全满足交易条件才给出买卖信号，小幅震荡一律观望；
给出信号需要写明完整判断依据；
观望仅简短回复：暂无交易机会，不要长篇文字。

2. 每日17点收盘总结模式：
完整复盘全天走势，分3-5个维度说明今日适合买入/卖出/观望的全部原因，条理清晰适合微信阅读。

要求：禁止过时知识库数据，语言通俗简洁，无多余客套话术。
"""
    user_msg = f"""
当前时间：{current_time_str}
任务类型：{"收盘全日复盘总结" if is_close_summary else "盘中实时巡检"}
标的：腾讯控股 00700.HK
"""
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_msg}
        ],
        "temperature": 0.2,
        "enable_search": True,
        "max_tokens": 1800
    }
    try:
        resp = requests.post("https://api.deepseek.com/v1/chat/completions", json=payload, headers=headers, timeout=60)
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]
    except Exception as e:
        err = f"AI调用出错：{str(e)}"
        print(err)
        return err

def main():
    now = datetime.now()
    now_str = now.strftime("%Y-%m-%d %H:%M:%S")
    today_date = now.strftime("%Y-%m-%d")
    hour = now.hour
    minute = now.minute

    # 读取状态
    state = load_signal_state()
    # 日期不一样，代表新一天，全部重置计数
    if state["today_date"] != today_date:
        state = reset_daily_state(today_date)

    is_close_task = (hour == 17 and minute == 0)
    analysis_text = get_stock_analysis(now_str, is_close_task)

    # 场景1：收盘总结推送，不计入每日5次限额
    if is_close_task:
        send_wechat(title="📅 腾讯控股每日收盘完整研判", content=analysis_text)
        save_signal_state(state)
        return

    # 场景2：盘中巡检判断买卖信号
    has_buy_signal = "【买入信号】" in analysis_text
    has_sell_signal = "【卖出信号】" in analysis_text

    if has_buy_signal or has_sell_signal:
        # 判断今日提醒次数是否已满5次
        if state["alert_count"] >= DAILY_MAX_ALERT:
            print(f"今日交易提醒已达上限{DAILY_MAX_ALERT}条，停止推送")
            save_signal_state(state)
            return

        # 推送本次提醒
        send_wechat(title="🚨 腾讯交易时机提醒", content=analysis_text)
        # 计数+1
        state["alert_count"] += 1
        save_signal_state(state)
    else:
        # 观望状态，不推送
        print("暂无交易信号，静默等待")
        save_signal_state(state)

if __name__ == "__main__":
    main()
