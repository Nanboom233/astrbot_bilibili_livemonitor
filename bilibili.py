import aiohttp
import os
from datetime import datetime
from astrbot.api import logger
from templates import MessageTemplates

class BilibiliLiveRoom:
    _session: aiohttp.ClientSession = None

    @classmethod
    async def get_session(cls):
        if cls._session is None or cls._session.closed:
            cls._session = aiohttp.ClientSession(headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36",
                "Referer": "https://live.bilibili.com/",
                "Accept-Encoding": "gzip, deflate"
            })
        return cls._session

    @classmethod
    async def close_session(cls):
        if cls._session and not cls._session.closed:
            try:
                await cls._session.close()
            except Exception as e:
                logger.error(f"关闭会话失败: {str(e)}")

    def __init__(self, room_id: str, anchor_name: str):
        self.room_id = str(room_id)
        self.anchor_name = str(anchor_name)
        self.last_status = None
        self.last_check_time = None
        self.live_start_time = None
        self.has_sent_live_notice = False
        self.room_title = "无标题"
        self.room_url = f"https://live.bilibili.com/{room_id}"
        self.cover_url = ""

    async def _get_room_init(self):
        try:
            session = await self.get_session()
            url = f"https://api.live.bilibili.com/room/v1/Room/room_init?id={self.room_id}"
            async with session.get(url, timeout=10) as resp:
                data = await resp.json()
                if data.get('code') == 0:
                    return data['data']
        except Exception as e:
            logger.error(f"获取直播间{self.room_id}基础信息失败: {str(e)}")
        return None

    async def _get_room_info(self):
        try:
            session = await self.get_session()
            url = f"https://api.live.bilibili.com/room/v1/Room/get_info?room_id={self.room_id}"
            async with session.get(url, timeout=10) as resp:
                data = await resp.json()
                if data.get('code') == 0:
                    return data['data']
        except Exception as e:
            logger.error(f"获取直播间{self.room_id}详细信息失败: {str(e)}")
        return None

    async def update_info(self) -> bool | dict:
        try:
            init_data = await self._get_room_init()
            if not init_data:
                return False
            
            room_data = await self._get_room_info()
            
            live_status = init_data.get('live_status', 0)
            live_time = init_data.get('live_time')
            
            if room_data:
                self.room_title = room_data.get('title', '无标题')
                self.cover_url = room_data.get('user_cover', '')

            is_new_live, is_new_offline = self._update_status(live_status, live_time)
            return {
                "is_new_live": is_new_live,
                "is_new_offline": is_new_offline,
                "current_status": live_status
            }
        except Exception as e:
            logger.error(f"更新直播间{self.room_id}信息失败: {str(e)}")
        return False

    async def download_cover(self):
        if not self.cover_url:
            return None
        save_dir = "covers"
        new_name = f"{self.room_id}.jpg"
        os.makedirs(save_dir, exist_ok=True)
        save_path = os.path.join(save_dir, new_name)
        
        try:
            session = await self.get_session()
            async with session.get(self.cover_url, timeout=15) as resp:
                resp.raise_for_status()
                with open(save_path, 'wb') as f:
                    f.write(await resp.read())
            return save_path
        except Exception as e:
            logger.error(f"异步下载直播间{self.room_id}封面失败: {str(e)}")
            return None

    def _update_status(self, current_status, live_time_str):
        self.last_check_time = datetime.now()
        
        is_new_live = False
        is_new_offline = False

        if self.last_status is None:
            self.last_status = current_status
            if current_status == 1:
                self._parse_live_time(live_time_str)
                self.has_sent_live_notice = True
            else:
                self.has_sent_live_notice = False
            return False, False 

        if current_status != self.last_status:
            self.last_status = current_status
            if current_status == 1:
                if not self.has_sent_live_notice:
                    self._parse_live_time(live_time_str)
                    is_new_live = True
            else:
                self.has_sent_live_notice = False
                self.live_start_time = None
                is_new_offline = True

        return is_new_live, is_new_offline

    def _parse_live_time(self, live_time_str):
        if not live_time_str:
            self.live_start_time = datetime.now()
            return
        try:
            self.live_start_time = datetime.strptime(live_time_str, "%Y-%m-%d %H:%M:%S")
        except (ValueError, TypeError) as e:
            logger.warning(f"解析直播间{self.room_id}开播时间失败，使用当前时间替代: {e}")
            self.live_start_time = datetime.now()

    async def get_formatted_info(self) -> str:
        success = await self.update_info()
        if not success:
            return MessageTemplates.msg_live_info_fail.render(
                anchor_name=self.anchor_name,
                room_id=self.room_id
            )
        
        last_check_time = self.last_check_time.strftime('%Y-%m-%d %H:%M:%S') if self.last_check_time else "未知"
        
        if self.last_status == 1:
            if self.live_start_time:
                duration_td = datetime.now() - self.live_start_time
                hours, remainder = divmod(duration_td.total_seconds(), 3600)
                minutes, seconds = divmod(remainder, 60)
                start_time = self.live_start_time.strftime('%Y-%m-%d %H:%M:%S')
                duration = f"{int(hours)}小时{int(minutes)}分钟{int(seconds)}秒"
            else:
                start_time = "未知"
                duration = "未知"
            
            return MessageTemplates.msg_live_info_live.render(
                anchor_name=self.anchor_name,
                room_id=self.room_id,
                room_title=self.room_title,
                room_url=self.room_url,
                last_check_time=last_check_time,
                start_time=start_time,
                duration=duration
            )
        else:
            return MessageTemplates.msg_live_info_offline.render(
                anchor_name=self.anchor_name,
                room_id=self.room_id,
                room_title=self.room_title,
                room_url=self.room_url,
                last_check_time=last_check_time
            )

