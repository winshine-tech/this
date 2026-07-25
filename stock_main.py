import os
import requests
import json
from datetime import datetime

# 环境变量密钥
DEEPSEEK_KEY = os.getenv("DEEPSEEK_API_KEY")
SEND_KEY = os.getenv("SERVER_SENDKEY")

# ===================== 工具1：判断港股交易日 周末拦截 =====================
def is_hk_trading_day(check_date: datetime) -> bool:
    week_day = check_date.weekday()
    # 5=周六，6=周日，非交易日
    if week_day >= 5:
        return False
    # 可自行补充节假日日期黑名单
    return True

# ===================== 工具2：新浪港股接口获取00700行情 =====================
def get_sina_hk_data():
    try:
        # 新浪港股公开接口 00700腾讯控股
        url = "https://hq.sinajs.cn/list=hk00700"
        resp = requests.get(url, timeout=8)
        resp.encoding = "gbk"
        raw_text = resp.text
        # 截取数据部分
        data_part = raw_text.split('"')[1]
        arr = data_part.split(",")
        return {
            "source": "新浪港股",
            "price": float(arr[2]) if arr[2] else 0,
            "prev_close": float(arr[3]) if arr[3] else 0,
            "open": float(arr[4]) if arr[4] else 0,
            "high": float(arr[5]) if arr[5] else 0,
            "low": float(arr[6]) if arr[6] else 0,
            "volume": int(arr[10]) if arr[10] else 0,
            "change": round(float(arr[2]) - float(arr[3]), 2),
            "change_percent": round((float(arr[2]) - float(arr[3])) / float(arr[3]) * 100, 2)
        }
    except Exception as e:
        return {"error": f"新浪接口失效：{str(e)}"}

# ===================== 工具3：腾讯财经接口获取00700行情 =====================
def get_qq_finance_hk_data():
    try:
        url = "https://stockapi.qq.com/v1/hk/stock?code=00700"
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(url, headers=headers, timeout=8)
        res_json = resp.json()
        data = res_json.get("data", {})
        return {
            "source": "腾讯财经",
            "price": data.get("now", 0),
            "prev_close": data.get("close_yest", 0),
            "open": data.get("open", 0),
            "high": data.get("high", 0),
            "low": data.get("low", 0),
            "volume": data.get("volume", 0),
            "change": data.get("diff", 0),
            "change_percent": data.get("diff_rate", 0)
        }
    except Exception as e:
        return {"error": f"腾讯财经接口失效：{str(e)}"}

# ===================== 工具4：双数据源合并行情 =====================
def get_merge_stock_data():
    sina = get_sina_hk_data()
    qq = get_qq_finance_hk_data()
    valid_data_list = []
    if "error" not in sina:
        valid_data_list.append(sina)
    if "error" not in qq:
        valid_data_list.append(qq)
    # 两个接口全部失效
    if len(valid_data_list) == 0:
        return {"error": "新浪、腾讯财经双行情接口全部获取失败，无行情数据"}
    # 优先取新浪为主数据，附带腾讯数据作为参考
    main_data = valid_data_list[0]
    return {
        "main_source": main_data["source"],
        "reference_source": valid_data_list[1]["source"] if len(valid_data_list)>=2 else "无备用数据源",
        "price": main_data["price"],
        "prev_close": main_data["prev_close"],
        "open": main_data["open"],
        "high": main_data["high"],
        "low": main_data["low"],
        "volume": main_data["volume"],
        "change": main_data["change"],
        "change_percent": main_data["change_percent"],
        "all_raw": valid_data_list
    }

# ===================== 工具5：微信Server酱推送 =====================
def send_wechat(title: str, content: str):
    if not SEND_KEY:
        print("未配置SERVER_SENDKEY，跳过推送")
        return
    try:
        url = f"https://sctapi.ftqq.com/{SEND_KEY}.send"
        post_data = {"title": title, "desp": content}
        requests.post(url, data=post_data, timeout=15)
        print(f"微信推送完成 | {title}")
    except Exception as e:
        print(f"微信推送异常: {str(e)}")

# ===================== 工具6：DeepSeek分析整合行情 =====================
def get_stock_analysis(current_time_str: str, merge_data: dict, is_close_summary: bool = False):
    # 双接口全部失效，直接返回错误
    if "error" in merge_data:
        return f"【行情获取失败】{merge_data['error']}，无法生成行情研判"

    # 格式化完整双数据源行情文本
    stock_info_text = f"""
===== 腾讯控股 00700.HK 双渠道实时行情汇总 =====
采集时间：{current_time_str}
主数据源：{merge_data['main_source']}
参考数据源：{merge_data['reference_source']}
现价：{merge_data['price']} HKD
昨日收盘价：{merge_data['prev_close']} HKD
今日开盘价：{merge_data['open']} HKD
日内最高价：{merge_data['high']} HKD
日内最低价：{merge_data['low']} HKD
今日总成交量：{merge_data['volume']}
涨跌金额：{merge_data['change']} HKD
涨跌幅：{merge_data['change_percent']} %

【强制规则】仅依据上面两条财经接口提供的真实数字分析，禁止编造分时、资金大单、新闻、政策、版号等不存在信息，无数据支撑只能输出【观望持有】。
"""

    system_prompt = """
你是港股专业短线分析师，严格遵守以下硬性约束：
1. 所有分析只能依托本次给到的新浪+腾讯财经真实行情数据，严禁虚构任何未提供的数据；
2. 单个自然交易日，最多合计输出5次【买入信号】/【卖出信号】，达到上限后当日剩余时段统一输出【观望持有】；
3. 小幅震荡、无明确多空支撑压力，一律输出【观望持有】；只有出现清晰趋势才给出交易信号；
4. 周六周日休市直接判定观望，不产生任何买卖建议。

两种工作模式：
① 盘中5分钟巡检：仅三选一输出【买入信号】/【卖出信号】/【观望持有】；有信号写明数据依据，观望只写“暂无交易机会”。
② 17点收盘总结：完整复盘当日全部行情数据，分3-5条多空逻辑，本条推送不计入单日5次提醒额度。
文字精简直白，无多余废话。
"""
    user_msg = f"""
{stock_info_text}
任务类型：{"收盘全日复盘总结" if is_close_summary else "盘中实时行情巡检"}
基于以上两套官方财经接口真实数据，给出客观行情研判。
"""

    headers = {
        "Authorization": f"Bearer {DEEPSEEK_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "deepseek-v4-flash",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_msg}
        ],
        "temperature": 0.2,
        "max_tokens": 1800
    }
    try:
        resp = requests.post("https://api.deepseek.com/v1/chat/completions", json=payload, headers=headers, timeout=60)
        print("DeepSeek状态码:", resp.status_code)
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]
    except Exception as e:
        resp_text = resp.text if "resp" in locals() else "无返回内容"
        return f"AI调用异常：{str(e)}，接口返回原始信息：{resp_text}"

# ===================== 主程序入口 =====================
def main():
    now = datetime.now()
    now_str = now.strftime("%Y-%m-%d %H:%M:%S")
    hour = now.hour
    minute = now.minute

    # 1. 周末直接终止程序
    if not is_hk_trading_day(now):
        print(f"{now_str} 当前为周末休市，程序直接退出，不执行行情分析")
        return

    # 2. 拉取新浪+腾讯双接口合并行情
    stock_data = get_merge_stock_data()

    # 3. 判断是否17点收盘总结任务
    is_close_task = (hour == 17 and minute == 0)

    # 4. 调用AI分析
    analysis_result = get_stock_analysis(now_str, stock_data, is_close_task)

    # 5. 区分推送逻辑
    if is_close_task:
        send_wechat("📅 腾讯控股每日收盘完整研判", analysis_result)
    else:
        signal_exist = "【买入信号】" in analysis_result or "【卖出信号】" in analysis_result
        if signal_exist:
            send_wechat("🚨 腾讯交易时机提醒", analysis_result)
        else:
            print("当前无有效交易信号，静默不推送消息")

if __name__ == "__main__":
    main()
