from __future__ import annotations

from typing import Optional

from astrbot.api import AstrBotConfig
from astrbot.api import logger


class MessageTemplates:
    """集中管理所有的模板实例化和默认文本"""
    _initialized = False

    # Templates
    msg_live_start: MessageTemplate
    msg_live_end: MessageTemplate
    msg_live_info_fail: MessageTemplate
    msg_live_info_offline: MessageTemplate
    msg_live_info_live: MessageTemplate
    msg_sub_success: MessageTemplate
    msg_sub_exist: MessageTemplate
    msg_unsub_success: MessageTemplate
    msg_unsub_fail: MessageTemplate
    msg_no_subs: MessageTemplate
    msg_all_info_header: MessageTemplate
    msg_sub_list: MessageTemplate
    msg_cover_fail: MessageTemplate
    
    # Qlamp Templates
    msg_qlamp_set_success: MessageTemplate
    msg_qlamp_not_set: MessageTemplate
    msg_qlamp_not_live: MessageTemplate
    msg_qlamp_record_success: MessageTemplate
    msg_qlamp_list_empty: MessageTemplate
    msg_qlamp_list_header: MessageTemplate
    msg_qlamp_list_group: MessageTemplate
    msg_qlamp_list_item: MessageTemplate
    msg_qlamp_clear_success: MessageTemplate
    msg_qlamp_clear_all_success: MessageTemplate
    msg_qlamp_clear_fail: MessageTemplate

    class MessageTemplate:
        """封装模板文本，统一处理格式化并提供错误回退机制"""
        template_str: str
        default_template: str

        def __init__(self, template_str: Optional[str], default_template: str):
            self.template_str = template_str if template_str else default_template
            self.default_template = default_template

        def render(self, **kwargs) -> str:
            """渲染模板，如果失败则回退到默认模板"""
            try:
                return self.template_str.format(**kwargs)
            except KeyError as e:
                logger.error(f"模板渲染缺少参数: {e}。当前模板: {self.template_str}")
                # 尝试使用默认模板
                try:
                    return self.default_template.format(**kwargs)
                except Exception as e2:
                    logger.critical(f"默认模板渲染也失败！返回未格式化的默认模板。错误: {e2}")
                    return self.default_template
            except Exception as e:
                logger.error(f"模板渲染未知错误 ({e})。将使用默认模板。")
                try:
                    return self.default_template.format(**kwargs)
                except Exception:
                    return self.default_template

        def __repr__(self):
            return f"<MessageTemplate str='{self.template_str[:20]}...'>"

    @classmethod
    def update_templates(cls, config: AstrBotConfig):
        cls.msg_live_start = MessageTemplates.MessageTemplate(
            template_str=config.get("msg_live_start", None),
            default_template=(
                "{anchor_name} 开播了喵！\n"
                "标题：{room_title}\n"
                "传送门: {room_url}"
            )
        )
        cls.msg_live_end = MessageTemplates.MessageTemplate(
            template_str=config.get("msg_live_end", None),
            default_template="{anchor_name} 的直播已结束喵。"
        )
        cls.msg_live_info_fail = MessageTemplates.MessageTemplate(
            template_str=config.get("msg_live_info_fail", None),
            default_template="直播间{room_id}（{anchor_name}）：无法获取直播信息，请稍后再试"
        )
        cls.msg_live_info_offline = MessageTemplates.MessageTemplate(
            template_str=config.get("msg_live_info_offline", None),
            default_template=(
                "直播间ID: {room_id}\n"
                "主播: {anchor_name}\n"
                "状态: 未开播\n"
                "标题: {room_title}\n"
                "最后检查时间: {last_check_time}\n"
                "直播间链接: {room_url}"
            )
        )
        cls.msg_live_info_live = MessageTemplates.MessageTemplate(
            template_str=config.get("msg_live_info_live", None),
            default_template=(
                "直播间ID: {room_id}\n"
                "主播: {anchor_name}\n"
                "状态: 直播中\n"
                "开播时间: {start_time}\n"
                "直播时长: {duration}\n"
                "标题: {room_title}\n"
                "最后检查时间: {last_check_time}\n"
                "直播间链接: {room_url}"
            )
        )
        cls.msg_sub_success = MessageTemplates.MessageTemplate(
            template_str=config.get("msg_sub_success", None),
            default_template="已为会话 {sid} 订阅直播间 {live_id}({anchor_name})"
        )
        cls.msg_sub_exist = MessageTemplates.MessageTemplate(
            template_str=config.get("msg_sub_exist", None),
            default_template="会话 {sid} 已订阅过该直播间"
        )
        cls.msg_unsub_success = MessageTemplates.MessageTemplate(
            template_str=config.get("msg_unsub_success", None),
            default_template="已取消会话 {sid} 对直播间 {live_id} 的订阅"
        )
        cls.msg_unsub_fail = MessageTemplates.MessageTemplate(
            template_str=config.get("msg_unsub_fail", None),
            default_template="未找到对应的订阅记录"
        )
        cls.msg_no_subs = MessageTemplates.MessageTemplate(
            template_str=config.get("msg_no_subs", None),
            default_template="当前暂无订阅任何直播间"
        )
        cls.msg_all_info_header = MessageTemplates.MessageTemplate(
            template_str=config.get("msg_all_info_header", None),
            default_template="所有直播间状态\n\n"
        )
        cls.msg_sub_list = MessageTemplates.MessageTemplate(
            template_str=config.get("msg_sub_list", None),
            default_template="\n订阅的会话: {sids_str}"
        )
        cls.msg_cover_fail = MessageTemplates.MessageTemplate(
            template_str=config.get("msg_cover_fail", None),
            default_template="<获取封面失败>"
        )
        cls.msg_qlamp_set_success = MessageTemplates.MessageTemplate(
            template_str=config.get("msg_qlamp_set_success", None),
            default_template="已将本会话的默认切片直播间设置为 {live_id}"
        )
        cls.msg_qlamp_not_set = MessageTemplates.MessageTemplate(
            template_str=config.get("msg_qlamp_not_set", None),
            default_template="本会话尚未设置默认直播间，请使用 qlamp_set 命令设置"
        )
        cls.msg_qlamp_not_live = MessageTemplates.MessageTemplate(
            template_str=config.get("msg_qlamp_not_live", None),
            default_template="当前直播间 {live_id} 未开播或无法获取开播时间"
        )
        cls.msg_qlamp_record_success = MessageTemplates.MessageTemplate(
            template_str=config.get("msg_qlamp_record_success", None),
            default_template="切片记录成功！\n场次ID: {session_id}\n时间节点: {time_offset}\n描述: {description}"
        )
        cls.msg_qlamp_list_empty = MessageTemplates.MessageTemplate(
            template_str=config.get("msg_qlamp_list_empty", None),
            default_template="暂无切片记录"
        )
        cls.msg_qlamp_list_header = MessageTemplates.MessageTemplate(
            template_str=config.get("msg_qlamp_list_header", None),
            default_template="切片记录 第 {page}/{total_pages} 页："
        )
        cls.msg_qlamp_list_group = MessageTemplates.MessageTemplate(
            template_str=config.get("msg_qlamp_list_group", None),
            default_template="\n\n📺 {anchor_name} - {room_title}\n🕒 开播: {start_time} (ID: {session_id})"
        )
        cls.msg_qlamp_list_item = MessageTemplates.MessageTemplate(
            template_str=config.get("msg_qlamp_list_item", None),
            default_template="\n  [{time_offset}] {description}"
        )
        cls.msg_qlamp_clear_success = MessageTemplates.MessageTemplate(
            template_str=config.get("msg_qlamp_clear_success", None),
            default_template="已成功删除场次 {session_id} 的切片记录。"
        )
        cls.msg_qlamp_clear_all_success = MessageTemplates.MessageTemplate(
            template_str=config.get("msg_qlamp_clear_all_success", None),
            default_template="已成功清空本会话的所有切片记录。"
        )
        cls.msg_qlamp_clear_fail = MessageTemplates.MessageTemplate(
            template_str=config.get("msg_qlamp_clear_fail", None),
            default_template="未找到对应场次 {session_id} 的切片记录。"
        )
        if not cls._initialized:
            cls._initialized = True

    @classmethod
    def get_all_templates(cls) -> dict[str, MessageTemplates.MessageTemplate]:
        """
        [Class Method] 获取当前类中定义的所有模板。
        可以直接调用 MessageTemplates.get_all_templates()
        """
        # 1. 检查是否执行过 update_templates
        if not cls._initialized:
            logger.error("MessageTemplates 尚未初始化，请先调用 update_templates。")
            return {}

        # 2. 遍历类属性 (cls.__dict__) 而不是实例属性
        # 因为在 update_templates 中，你是用 cls.xxx = ... 赋值的
        return {
            key: value
            for key, value in cls.__dict__.items()
            if isinstance(value, cls.MessageTemplate)
        }
