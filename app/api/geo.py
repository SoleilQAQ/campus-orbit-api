# app/api/geo.py
"""地理编码接口 - 反向地理编码获取城市信息"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

import httpx
from fastapi import APIRouter, Query, Request
from pydantic import BaseModel, Field

# 中国主要城市拼音映射表
CITY_PINYIN_MAP = {
    "北京市": "beijing", "北京": "beijing",
    "上海市": "shanghai", "上海": "shanghai",
    "天津市": "tianjin", "天津": "tianjin",
    "重庆市": "chongqing", "重庆": "chongqing",
    "广州市": "guangzhou", "广州": "guangzhou",
    "深圳市": "shenzhen", "深圳": "shenzhen",
    "杭州市": "hangzhou", "杭州": "hangzhou",
    "南京市": "nanjing", "南京": "nanjing",
    "武汉市": "wuhan", "武汉": "wuhan",
    "成都市": "chengdu", "成都": "chengdu",
    "西安市": "xian", "西安": "xian",
    "长沙市": "changsha", "长沙": "changsha",
    "苏州市": "suzhou", "苏州": "suzhou",
    "青岛市": "qingdao", "青岛": "qingdao",
    "大连市": "dalian", "大连": "dalian",
    "厦门市": "xiamen", "厦门": "xiamen",
    "宁波市": "ningbo", "宁波": "ningbo",
    "无锡市": "wuxi", "无锡": "wuxi",
    "福州市": "fuzhou", "福州": "fuzhou",
    "济南市": "jinan", "济南": "jinan",
    "郑州市": "zhengzhou", "郑州": "zhengzhou",
    "合肥市": "hefei", "合肥": "hefei",
    "南昌市": "nanchang", "南昌": "nanchang",
    "长春市": "changchun", "长春": "changchun",
    "哈尔滨市": "haerbin", "哈尔滨": "haerbin",
    "沈阳市": "shenyang", "沈阳": "shenyang",
    "石家庄市": "shijiazhuang", "石家庄": "shijiazhuang",
    "太原市": "taiyuan", "太原": "taiyuan",
    "昆明市": "kunming", "昆明": "kunming",
    "贵阳市": "guiyang", "贵阳": "guiyang",
    "南宁市": "nanning", "南宁": "nanning",
    "海口市": "haikou", "海口": "haikou",
    "兰州市": "lanzhou", "兰州": "lanzhou",
    "银川市": "yinchuan", "银川": "yinchuan",
    "西宁市": "xining", "西宁": "xining",
    "拉萨市": "lasa", "拉萨": "lasa",
    "乌鲁木齐市": "wulumuqi", "乌鲁木齐": "wulumuqi",
    "呼和浩特市": "huhehaote", "呼和浩特": "huhehaote",
    "香港": "hongkong", "澳门": "macau", "台北市": "taipei", "台北": "taipei",
    "珠海市": "zhuhai", "珠海": "zhuhai",
    "东莞市": "dongguan", "东莞": "dongguan",
    "佛山市": "foshan", "佛山": "foshan",
    "中山市": "zhongshan", "中山": "zhongshan",
    "惠州市": "huizhou", "惠州": "huizhou",
    "温州市": "wenzhou", "温州": "wenzhou",
    "绍兴市": "shaoxing", "绍兴": "shaoxing",
    "嘉兴市": "jiaxing", "嘉兴": "jiaxing",
    "金华市": "jinhua", "金华": "jinhua",
    "台州市": "taizhou", "台州": "taizhou",
    "常州市": "changzhou", "常州": "changzhou",
    "南通市": "nantong", "南通": "nantong",
    "徐州市": "xuzhou", "徐州": "xuzhou",
    "扬州市": "yangzhou", "扬州": "yangzhou",
    "烟台市": "yantai", "烟台": "yantai",
    "潍坊市": "weifang", "潍坊": "weifang",
    "临沂市": "linyi", "临沂": "linyi",
    "洛阳市": "luoyang", "洛阳": "luoyang",
    "唐山市": "tangshan", "唐山": "tangshan",
    "保定市": "baoding", "保定": "baoding",
    "廊坊市": "langfang", "廊坊": "langfang",
    "秦皇岛市": "qinhuangdao", "秦皇岛": "qinhuangdao",
    "邯郸市": "handan", "邯郸": "handan",
    "包头市": "baotou", "包头": "baotou",
    "鄂尔多斯市": "eerduosi", "鄂尔多斯": "eerduosi",
    "吉林市": "jilin", "吉林": "jilin",
    "大庆市": "daqing", "大庆": "daqing",
    "鞍山市": "anshan", "鞍山": "anshan",
    "抚顺市": "fushun", "抚顺": "fushun",
    "芜湖市": "wuhu", "芜湖": "wuhu",
    "蚌埠市": "bengbu", "蚌埠": "bengbu",
    "淮南市": "huainan", "淮南": "huainan",
    "马鞍山市": "maanshan", "马鞍山": "maanshan",
    "泉州市": "quanzhou", "泉州": "quanzhou",
    "漳州市": "zhangzhou", "漳州": "zhangzhou",
    "九江市": "jiujiang", "九江": "jiujiang",
    "赣州市": "ganzhou", "赣州": "ganzhou",
    "株洲市": "zhuzhou", "株洲": "zhuzhou",
    "湘潭市": "xiangtan", "湘潭": "xiangtan",
    "衡阳市": "hengyang", "衡阳": "hengyang",
    "岳阳市": "yueyang", "岳阳": "yueyang",
    "常德市": "changde", "常德": "changde",
    "宜昌市": "yichang", "宜昌": "yichang",
    "襄阳市": "xiangyang", "襄阳": "xiangyang",
    "荆州市": "jingzhou", "荆州": "jingzhou",
    "黄石市": "huangshi", "黄石": "huangshi",
    "绵阳市": "mianyang", "绵阳": "mianyang",
    "德阳市": "deyang", "德阳": "deyang",
    "南充市": "nanchong", "南充": "nanchong",
    "宜宾市": "yibin", "宜宾": "yibin",
    "泸州市": "luzhou", "泸州": "luzhou",
    "遵义市": "zunyi", "遵义": "zunyi",
    "柳州市": "liuzhou", "柳州": "liuzhou",
    "桂林市": "guilin", "桂林": "guilin",
    "三亚市": "sanya", "三亚": "sanya",
    "曲靖市": "qujing", "曲靖": "qujing",
    "玉溪市": "yuxi", "玉溪": "yuxi",
    "大理市": "dali", "大理": "dali",
    "丽江市": "lijiang", "丽江": "lijiang",
    "天水市": "tianshui", "天水": "tianshui",
    "酒泉市": "jiuquan", "酒泉": "jiuquan",
    "威海市": "weihai", "威海": "weihai",
    "日照市": "rizhao", "日照": "rizhao",
    "泰安市": "taian", "泰安": "taian",
    "济宁市": "jining", "济宁": "jining",
    "聊城市": "liaocheng", "聊城": "liaocheng",
    "德州市": "dezhou", "德州": "dezhou",
    "滨州市": "binzhou", "滨州": "binzhou",
    "菏泽市": "heze", "菏泽": "heze",
    "枣庄市": "zaozhuang", "枣庄": "zaozhuang",
    "东营市": "dongying", "东营": "dongying",
    "淄博市": "zibo", "淄博": "zibo",
    "莱芜市": "laiwu", "莱芜": "laiwu",
}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _get_city_pinyin(city_name: str) -> str:
    """获取城市拼音"""
    # 先尝试直接匹配
    if city_name in CITY_PINYIN_MAP:
        return CITY_PINYIN_MAP[city_name]
    
    # 尝试去掉"市"后匹配
    if city_name.endswith("市"):
        short_name = city_name[:-1]
        if short_name in CITY_PINYIN_MAP:
            return CITY_PINYIN_MAP[short_name]
    
    # 使用简单的拼音转换（基于首字母）
    # 这里返回城市名本身，让天气 API 自己处理
    return city_name.replace("市", "")


router = APIRouter(prefix="/api/geo", tags=["geo"])


class GeoData(BaseModel):
    """地理信息数据"""
    province: str
    city: str
    district: str
    cityPinyin: str = Field(..., alias="cityPinyin")


class GeoError(BaseModel):
    """地理编码错误"""
    code: str
    detail: str


class GeoResponse(BaseModel):
    """地理编码响应"""
    success: bool
    message: str
    timestamp: str
    data: Optional[GeoData] = None
    error: Optional[GeoError] = None


@router.get("/reverse", response_model=GeoResponse)
async def reverse_geocode(
    request: Request,
    lat: float = Query(..., ge=-90, le=90, description="纬度"),
    lng: float = Query(..., ge=-180, le=180, description="经度"),
):
    """
    反向地理编码 - 根据经纬度获取城市信息
    
    使用 Nominatim (OpenStreetMap) API 进行反向地理编码
    """
    timestamp = _utc_now_iso()
    
    # 简单检查是否在中国大陆范围内（粗略范围）
    if not (18 <= lat <= 54 and 73 <= lng <= 135):
        return GeoResponse(
            success=False,
            message="无法解析该位置的城市信息",
            timestamp=timestamp,
            error=GeoError(
                code="GEOCODE_FAILED",
                detail="坐标超出中国大陆范围"
            )
        )
    
    try:
        # 使用 Nominatim API（免费，无需 API Key）
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                "https://nominatim.openstreetmap.org/reverse",
                params={
                    "lat": lat,
                    "lon": lng,
                    "format": "json",
                    "accept-language": "zh-CN",
                    "addressdetails": 1,
                },
                headers={
                    "User-Agent": "CampusOrbit/1.0 (Weather App)",
                }
            )
            
            if resp.status_code != 200:
                return GeoResponse(
                    success=False,
                    message="地理编码服务暂时不可用",
                    timestamp=timestamp,
                    error=GeoError(
                        code="SERVICE_UNAVAILABLE",
                        detail=f"API 返回状态码: {resp.status_code}"
                    )
                )
            
            data = resp.json()
            address = data.get("address", {})
            
            # 解析省份
            province = (
                address.get("state") or 
                address.get("province") or 
                address.get("region") or 
                ""
            )
            
            # 解析城市（优先级：city > county > town）
            city = (
                address.get("city") or 
                address.get("county") or 
                address.get("town") or
                address.get("municipality") or
                ""
            )
            
            # 解析区县
            district = (
                address.get("district") or 
                address.get("suburb") or 
                address.get("neighbourhood") or
                address.get("village") or
                ""
            )
            
            if not city:
                return GeoResponse(
                    success=False,
                    message="无法解析该位置的城市信息",
                    timestamp=timestamp,
                    error=GeoError(
                        code="GEOCODE_FAILED",
                        detail="未能从坐标中解析出城市信息"
                    )
                )
            
            # 获取城市拼音
            city_pinyin = _get_city_pinyin(city)
            
            return GeoResponse(
                success=True,
                message="获取城市信息成功",
                timestamp=timestamp,
                data=GeoData(
                    province=province,
                    city=city,
                    district=district,
                    cityPinyin=city_pinyin,
                )
            )
            
    except httpx.TimeoutException:
        return GeoResponse(
            success=False,
            message="地理编码服务请求超时",
            timestamp=timestamp,
            error=GeoError(
                code="TIMEOUT",
                detail="请求超时，请稍后重试"
            )
        )
    except Exception as e:
        return GeoResponse(
            success=False,
            message="地理编码服务异常",
            timestamp=timestamp,
            error=GeoError(
                code="INTERNAL_ERROR",
                detail=str(e)
            )
        )
