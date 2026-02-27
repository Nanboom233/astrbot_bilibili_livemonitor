import asyncio
import os
from datetime import datetime
from typing import Optional

import yaml
from astrbot.api import AstrBotConfig
from astrbot.api import logger
from astrbot.api.event import MessageChain
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register

from .bilibili import BilibiliLiveRoom
from .templates import MessageTemplates


def load_metadata():
    yaml_path = os.path.join(os.path.dirname(__file__), "metadata.yaml")
    if not os.path.exists(yaml_path):
        raise FileNotFoundError(f"metadata.yaml 未找到: {yaml_path}")

    with open(yaml_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if not data:
        raise ValueError("metadata.yaml 为空或格式错误")

    required_keys = ["name", "author", "desc", "version", "repo"]
    for key in required_keys:
        if key not in data:
            raise ValueError(f"metadata.yaml 缺少必要字段: {key}")

    return data


PLUGIN_META = load_metadata()


@register(
    PLUGIN_META["name"],
    PLUGIN_META["author"],
    PLUGIN_META["desc"],
    str(PLUGIN_META["version"]).lstrip("v"),
    PLUGIN_META["repo"]
)
class BilibiliLiveMonitor(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config

        self.rooms = {}
        try:
            self.check_interval = int(config.get("time", 60))
        except (ValueError, TypeError):
            self.check_interval = 60

        # 集中管理模板配置
        MessageTemplates.update_templates(config)
        self.running = True

    async def _get_subs(self) -> dict:
        subs = await self.get_kv_data("subs", {})
        # {"sids": [], "anchor_name": anchor_name}
        return {int(k): v for k, v in subs.items()}

    async def _save_subs(self, subs: dict):
        await self.put_kv_data("subs", {str(k): v for k, v in subs.items()})

    @filter.on_astrbot_loaded()
    async def load_subs(self):
        subs = await self._get_subs()
        for live_id, data in subs.items():
            self.rooms[live_id] = BilibiliLiveRoom(live_id, data.get("anchor_name", str(live_id)))

        asyncio.create_task(self.monitor_task())

    async def update_and_notify_room(self, room_id: int, room: BilibiliLiveRoom) -> Optional[dict]:
        result = await room.update_info()
        if not result:
            return None

        if result["is_new_live"]:
            save_path = await room.download_cover()

            msg_text = MessageTemplates.msg_live_start.render(
                anchor_name=room.anchor_name,
                room_title=room.room_title,
                room_url=room.room_url,
                room_id=room.room_id
            )

            message = MessageChain().message(msg_text)
            if save_path and os.path.exists(save_path):
                message.file_image(save_path)
            else:
                message.message(MessageTemplates.msg_cover_fail.render())

            subs = await self._get_subs()
            sids = subs.get(room_id, {}).get("sids", [])

            for sid in sids:
                try:
                    logger.debug(message.get_plain_text(True))
                    await self.context.send_message(sid, message)
                    logger.info(f"已向会话 {sid} 发送 {room.anchor_name} 开播通知")
                except Exception as e:
                    logger.error(f"向会话 {sid} 发送开播通知失败: {e}")

            room.has_sent_live_notice = True
            logger.info(f"直播间{room_id}({room.anchor_name})开播，已发送通知")

        elif result["is_new_offline"]:
            msg_text = MessageTemplates.msg_live_end.render(
                anchor_name=room.anchor_name,
                room_id=room.room_id
            )

            message = MessageChain().message(msg_text)

            subs = await self._get_subs()
            sids = subs.get(room_id, {}).get("sids", [])

            for sid in sids:
                try:
                    logger.debug(message.get_plain_text(True))
                    await self.context.send_message(sid, message)
                    logger.info(f"已向会话 {sid} 发送 {room.anchor_name} 下播通知")
                except Exception as e:
                    logger.error(f"向会话 {sid} 发送下播通知失败: {e}")

            logger.info(f"直播间{room_id}({room.anchor_name})已下播")

        return result

    async def monitor_task(self):
        while self.running:
            logger.debug("执行直播间监控任务")
            for room_id, room in list(self.rooms.items()):
                try:
                    await self.update_and_notify_room(room_id, room)
                except Exception as e:
                    logger.error(f"更新直播间 {room_id} 出错: {str(e)}")

            try:
                await asyncio.sleep(self.check_interval)
            except Exception as e:
                logger.error(f"休眠时出错: {str(e)}")
                await asyncio.sleep(60)

    @filter.permission_type(filter.PermissionType.ADMIN)
    @filter.command("live_sub")
    async def live_sub_command(self, event: AstrMessageEvent, sid: str, live_id: int,
                               anchor_name: Optional[str] = None):
        """订阅直播间通知。参数: sid 直播间ID [主播名称]"""
        subs = await self._get_subs()

        if live_id not in subs:
            subs[live_id] = {"sids": [], "anchor_name": anchor_name}
            self.rooms[live_id] = BilibiliLiveRoom(live_id, anchor_name or str(live_id))

        if sid not in subs[live_id]["sids"]:
            subs[live_id]["sids"].append(sid)
            await self._save_subs(subs)
            yield event.plain_result(MessageTemplates.msg_sub_success.render(
                sid=sid, live_id=live_id, anchor_name=anchor_name
            ))
        else:
            yield event.plain_result(MessageTemplates.msg_sub_exist.render(
                sid=sid, live_id=live_id
            ))

    @filter.permission_type(filter.PermissionType.ADMIN)
    @filter.command("live_unsub")
    async def live_unsub_command(self, event: AstrMessageEvent, sid: str, live_id: int):
        subs = await self._get_subs()
        if live_id in subs and sid in subs[live_id]["sids"]:
            subs[live_id]["sids"].remove(sid)
            if not subs[live_id]["sids"]:
                del subs[live_id]
                if live_id in self.rooms:
                    del self.rooms[live_id]
            await self._save_subs(subs)
            yield event.plain_result(MessageTemplates.msg_unsub_success.render(
                sid=sid, live_id=live_id
            ))
        else:
            yield event.plain_result(MessageTemplates.msg_unsub_fail.render(
                sid=sid, live_id=live_id
            ))

    async def get_live_info(self, room_id: Optional[int] = None):
        subs = await self._get_subs()

        if room_id and room_id in self.rooms:
            room = self.rooms[room_id]
            result = await self.update_and_notify_room(room_id, room)
            info = room.get_formatted_info(result)

            sids = subs.get(room_id, {}).get("sids", [])
            sids_str = ", ".join(sids) if sids else "无"
            info += MessageTemplates.msg_sub_list.render(sids_str=sids_str)

            return info
        else:
            if not self.rooms:
                return MessageTemplates.msg_no_subs.render()
            all_info = []
            for r_id, room in self.rooms.items():
                result = await self.update_and_notify_room(r_id, room)
                info = room.get_formatted_info(result)

                sids = subs.get(r_id, {}).get("sids", [])
                sids_str = ", ".join(sids) if sids else "无"
                info += MessageTemplates.msg_sub_list.render(sids_str=sids_str)

                all_info.append(info)
            return MessageTemplates.msg_all_info_header.render() + "\n\n".join(all_info)

    @filter.permission_type(filter.PermissionType.ADMIN)
    @filter.command("live_info")
    async def live_info_command(self, event: AstrMessageEvent, live_id: Optional[int] = None):
        """获取直播间信息。可选参数: 直播间ID"""
        info = await self.get_live_info(live_id)
        yield event.plain_result(info)

    @filter.permission_type(filter.PermissionType.ADMIN)
    @filter.command("qlamp_set")
    async def qlamp_set_command(self, event: AstrMessageEvent, live_id: int):
        umo = event.unified_msg_origin
        default_map = await self.get_kv_data("qlamp_default", {})
        default_map[umo] = live_id
        await self.put_kv_data("qlamp_default", default_map)
        yield event.plain_result(MessageTemplates.msg_qlamp_set_success.render(live_id=live_id))

    @filter.permission_type(filter.PermissionType.MEMBER)
    @filter.command("qlamp_list")
    async def qlamp_list_command(self, event: AstrMessageEvent, page: int = 1):
        umo = event.unified_msg_origin

        records = await self.get_kv_data("qlamp_records", [])

        # 仅过滤出当前会话(umo)的记录
        records = [r for r in records if r.get("umo") == umo]

        if not records:
            yield event.plain_result(MessageTemplates.msg_qlamp_list_empty.render())
            return

        # 按 session_id 分组，保证同一场次的切片在一起
        sessions = {}
        for r in reversed(records):  # 倒序遍历，最新的场次排在前面
            sid = r["session_id"]
            if sid not in sessions:
                # 尝试从 session_id 提取开播时间
                start_time_raw = sid.split("_")[-1] if "_" in sid else ""
                try:
                    start_time_dt = datetime.strptime(start_time_raw, "%Y%m%d%H%M%S")
                    start_time_str = start_time_dt.strftime("%Y-%m-%d %H:%M")
                except (ValueError, TypeError):
                    start_time_str = start_time_raw
                    
                sessions[sid] = {
                    "live_id": r.get("live_id", "未知"),
                    "room_title": r.get("room_title", "未知标题"),
                    "anchor_name": r.get("anchor_name", "未知主播"),
                    "start_time_str": start_time_str,
                    "records": []
                }
            sessions[sid]["records"].append(r)
            
        # 让每个场次内的记录按时间正序排列
        for sid in sessions:
            sessions[sid]["records"].reverse()

        session_list = list(sessions.values())

        items_per_page = 3  # 每页显示 3 个场次
        total_pages = (len(session_list) + items_per_page - 1) // items_per_page
        if total_pages == 0:
            total_pages = 1
            
        page = max(1, min(page, total_pages))
        start_idx = (page - 1) * items_per_page
        end_idx = start_idx + items_per_page
        
        page_sessions = session_list[start_idx:end_idx]

        result_text = MessageTemplates.msg_qlamp_list_header.render(page=page, total_pages=total_pages)
        for s in page_sessions:
            result_text += MessageTemplates.msg_qlamp_list_group.render(
                anchor_name=s["anchor_name"],
                room_title=s["room_title"],
                start_time=s["start_time_str"]
            )
            for r in s["records"]:
                result_text += MessageTemplates.msg_qlamp_list_item.render(
                    time_offset=r["time_offset"],
                    description=r["description"]
                )

        yield event.plain_result(result_text)

    @filter.permission_type(filter.PermissionType.MEMBER)
    @filter.command("qlamp")
    async def qlamp_command(self, event: AstrMessageEvent, description: str = "No description"):
        umo = event.unified_msg_origin
        default_map = await self.get_kv_data("qlamp_default", {})
        live_id = default_map.get(umo)

        if not live_id:
            yield event.plain_result(MessageTemplates.msg_qlamp_not_set.render())
            return

        room = self.rooms.get(live_id)
        if not room:
            room = BilibiliLiveRoom(live_id, str(live_id))

        # 强制更新一次以获取最新状态
        await room.update_info()

        if room.last_status != 1 or not room.live_start_time:
            yield event.plain_result(MessageTemplates.msg_qlamp_not_live.render(live_id=live_id))
            return

        duration_td = datetime.now() - room.live_start_time
        hours, remainder = divmod(duration_td.total_seconds(), 3600)
        minutes, seconds = divmod(remainder, 60)
        
        # 更为 user-friendly 的时间格式
        if hours > 0:
            time_offset = f"{int(hours)}:{int(minutes):02d}:{int(seconds):02d}"
        else:
            time_offset = f"{int(minutes):02d}:{int(seconds):02d}"

        session_id = f"{live_id}_{room.live_start_time.strftime('%Y%m%d%H%M%S')}"

        records = await self.get_kv_data("qlamp_records", [])
        records.append({
            "session_id": session_id,
            "live_id": live_id,
            "room_title": room.room_title,
            "anchor_name": room.anchor_name,
            "time_offset": time_offset,
            "description": description,
            "umo": umo,
            "timestamp": datetime.now().timestamp()
        })
        await self.put_kv_data("qlamp_records", records)

        yield event.plain_result(MessageTemplates.msg_qlamp_record_success.render(
            session_id=session_id,
            time_offset=time_offset,
            description=description
        ))

    async def terminate(self):
        self.running = False
        await BilibiliLiveRoom.close_session()
        logger.info("直播间监控插件已停止")
