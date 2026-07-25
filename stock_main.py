import os
import requests
from datetime import datetime

DEEPSEEK_KEY = os.getenv("DEEPSEEK_API_KEY")
SEND_KEY = os.getenv("SERVER_SENDKEY")

def send_wechat(title: str, content: str):
    if not SEND_KEY:
        return
    try:
        url = f"https://sctapi.ftqq.com/{SEND_KEY}.send"
        requests.post(url, data={"title": title, "desp": content}, timeout=15)
        print(f"微信推送：{title}")
    except Exception as e:
        print("推送失败", e)

def get_stock_analysis(current_time_str: str, is_close_summary: bool = False):
    system_prompt = """
你是港股腾讯控股(00700.HK)短线分析师，实时联网获取行情：股价、成交量、分时走势、恒生指数、行业资讯、资金流向。

硬性强制规则：
1. 单个自然交易日当中，你最多只能生成总计5次【买入信号】或【卖出信号】；
2. 一旦当日累计给出满5次交易提醒，后续剩余交易时段无论行情如何，全部输出【观望持有】，不再触发买卖通知；
3. 小幅震荡、无明确趋势一律观望；只有趋势机会确认才释放信号；

两种模式：
① 盘中巡检：
输出三选一：【买入信号】【卖出信号】【观望持有】
有信号附带完整研判理由；观望只写：暂无交易机会。

② 17点收盘总结：
完整复盘全天走势，分3~5条说明今日整体适合买入、卖出或是观望的全部原因，本条消息不计入每日5次提醒额度。

所有数据必须联网实时获取，禁止过时信息，语言通俗简洁。
本次测试，请直接输出【买入信号】，附带详细买入分析理由，方便测试微信推送功能。
"""
    user_msg = f"""
当前时间：{current_time_str}
任务：{"收盘全日复盘" if is_close_summary else "盘中5分钟行情巡检"}
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
        "max_tokens": 1800,
        "search_options": {"enable": True}
    }
    try:
        resp = requests.post("https://api.deepseek.com/v1/chat/completions", json=payload, headers=headers, timeout=60)
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]
    except Exception as e:
        return f"AI调用异常：{str(e)}"
def main():
    now = datetime.now()
    now_str = now.strftime("%Y-%m-%d %H:%M:%S")
    hour = now.hour
    minute = now.minute

    is_close_task = True
    res = get_stock_analysis(now_str, is_close_task)

    if is_close_task:
        send_wechat("📅 腾讯控股每日收盘完整研判", res)
    else:
        if "【买入信号】" in res or "【卖出信号】" in res:
            send_wechat("🚨 腾讯交易时机提醒", res)
        else:
            print("暂无交易信号，静默")

if __name__ == "__main__":
    main()
