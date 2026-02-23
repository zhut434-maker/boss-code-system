import streamlit as st
import sqlite3
import random
from datetime import datetime, timedelta
from streamlit_cookies_manager import EncryptedCookieManager

# -------------------------- 配置初始化 --------------------------
# 权限等级定义
PERMISSION_USER = 0       # 普通用户
PERMISSION_SUB_ADMIN = 1  # 次级管理员
PERMISSION_SUPER_ADMIN = 2# 超级管理员

# ========== Cookie持久化登录配置 ==========
cookies = EncryptedCookieManager(
    prefix="boss_code_system_",
    password="your_secure_password_123456"
)
if not cookies.ready():
    st.stop()

# 数据库初始化
def init_db():
    conn = sqlite3.connect("boss_code_system.db", check_same_thread=False)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            permission_level INTEGER DEFAULT 0,
            remain_receive_times INTEGER DEFAULT 1,
            create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS boss_codes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE NOT NULL,
            is_used INTEGER DEFAULT 0,
            receive_user_id INTEGER,
            receive_time TIMESTAMP,
            create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS receive_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            code_id INTEGER NOT NULL,
            code TEXT NOT NULL,
            receive_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    try:
        c.execute("INSERT INTO users (username, password, permission_level, remain_receive_times) VALUES (?, ?, ?, ?)",
                  ("admin", "admin123", PERMISSION_SUPER_ADMIN, 9999))
    except:
        pass
    conn.commit()
    return conn

# 统一解析Boss码
def parse_boss_codes(content):
    code_list = []
    lines = content.split("\n")
    for line in lines:
        codes_in_line = line.strip().split()
        for code in codes_in_line:
            code = code.strip()
            if len(code) == 5 and code.isalnum():
                code_list.append(code)
    code_list = list(set(code_list))
    return code_list

# 解析TXT文件
def parse_boss_code_txt(file_content):
    content = file_content.decode("utf-8")
    return parse_boss_codes(content)

# 数据库连接
conn = init_db()
c = conn.cursor()

# ========== 页面初始化：从Cookie自动恢复登录状态 ==========
if "logged_in" not in st.session_state:
    if cookies.get("user_id") and cookies.get("username") and cookies.get("permission_level"):
        st.session_state.logged_in = True
        st.session_state.user_id = int(cookies["user_id"])
        st.session_state.username = cookies["username"]
        st.session_state.permission_level = int(cookies["permission_level"])
    else:
        st.session_state.logged_in = False
        st.session_state.username = ""
        st.session_state.user_id = 0
        st.session_state.permission_level = PERMISSION_USER

# -------------------------- 页面 --------------------------
st.set_page_config(page_title="Boss码领取系统", page_icon="🎮", layout="wide")
st.title("🎮 Boss码自助领取系统")

# ========== 退出登录逻辑（最前置处理） ==========
if st.session_state.logged_in:
    if st.button("退出登录", key="logout_btn_top_right", use_container_width=True):
        # 清空Cookie和会话
        for key in list(cookies.keys()):
            del cookies[key]
        cookies.save()
        st.session_state.clear()
        st.rerun()

# 未登录状态：登录/注册/忘记密码
if not st.session_state.logged_in:
    # 新增忘记密码Tab
    tab1, tab2, tab3 = st.tabs(["用户登录", "账号注册", "忘记密码"])
    
    # 登录页
    with tab1:
        username = st.text_input("用户名", key="login_username")
        password = st.text_input("密码", type="password", key="login_password")
        remember_me = st.checkbox("记住我7天内免登录", value=True, key="remember_me")
        if st.button("登录", use_container_width=True, key="login_btn"):
            c.execute("SELECT id, username, password, permission_level FROM users WHERE username = ?", (username,))
            user = c.fetchone()
            if user and password == user[2]:
                st.session_state.logged_in = True
                st.session_state.user_id = user[0]
                st.session_state.username = user[1]
                st.session_state.permission_level = user[3]
                
                if remember_me:
                    expires = datetime.now() + timedelta(days=7)
                    cookies["user_id"] = str(user[0])
                    cookies["username"] = user[1]
                    cookies["permission_level"] = str(user[3])
                    cookies.expires = expires
                    cookies.save()
                
                st.success("登录成功！正在跳转...")
                st.rerun()
            else:
                st.error("账号或密码错误")
    
    # 注册页
    with tab2:
        new_username = st.text_input("设置用户名", key="register_username")
        new_password = st.text_input("设置密码", type="password", key="register_password")
        confirm = st.text_input("确认密码", type="password", key="register_confirm_pwd")
        if st.button("注册账号", use_container_width=True, key="register_btn"):
            if new_password != confirm:
                st.error("两次密码输入不一致")
            elif len(new_username) < 3:
                st.error("用户名至少3位")
            elif len(new_password) < 6:
                st.error("密码至少6位")
            else:
                try:
                    c.execute("INSERT INTO users (username, password) VALUES (?, ?)", (new_username, new_password))
                    conn.commit()
                    st.success("注册成功！请返回登录页登录")
                except sqlite3.IntegrityError:
                    st.error("用户名已存在，请更换")
    
    # ========== 新增：忘记密码重置页 ==========
    with tab3:
        st.subheader("重置账号密码")
        reset_username = st.text_input("请输入你的用户名", key="forget_username")
        new_pwd = st.text_input("设置新密码", type="password", key="forget_new_pwd")
        confirm_new_pwd = st.text_input("确认新密码", type="password", key="forget_confirm_pwd")
        
        if st.button("确认重置密码", type="primary", use_container_width=True, key="forget_reset_btn"):
            # 校验逻辑
            if not reset_username.strip():
                st.error("请输入用户名")
            elif new_pwd != confirm_new_pwd:
                st.error("两次密码输入不一致")
            elif len(new_pwd) < 6:
                st.error("新密码至少6位")
            else:
                # 检查用户名是否存在
                c.execute("SELECT id, username FROM users WHERE username = ?", (reset_username,))
                target_user = c.fetchone()
                if not target_user:
                    st.error("该用户名不存在！")
                else:
                    # 更新密码
                    c.execute("UPDATE users SET password = ? WHERE username = ?", (new_pwd, reset_username))
                    conn.commit()
                    st.success(f"用户【{reset_username}】的密码重置成功！请返回登录页使用新密码登录")

# 已登录状态
else:
    # 用户信息
    col1, col2 = st.columns([8, 2])
    with col1:
        role = "超级管理员" if st.session_state.permission_level == 2 else "次级管理员" if st.session_state.permission_level == 1 else "普通用户"
        st.subheader(f"欢迎 {st.session_state.username} | {role}")
    st.divider()

    # 管理员后台
    if st.session_state.permission_level >= 1:
        tabs = st.tabs(["Boss码管理", "用户管理", "领取记录", "库存统计"] + (["权限设置"] if st.session_state.permission_level == 2 else []))

        # ========== Boss码管理 ==========
        with tabs[0]:
            # 1. TXT文件上传导入
            st.subheader("📁 上传TXT文件导入（空格分隔）")
            f = st.file_uploader("选择存放Boss码的TXT文件", type="txt", key="code_uploader")
            if f and st.button("解析并导入TXT文件", type="primary", use_container_width=True, key="code_import_btn"):
                codes = parse_boss_code_txt(f.getvalue())
                if not codes:
                    st.error("未从文件中解析到有效Boss码（仅支持5位字母/数字组合）")
                else:
                    ok = 0
                    dup = 0
                    for cd in codes:
                        try:
                            c.execute("INSERT INTO boss_codes (code) VALUES (?)", (cd,))
                            ok += 1
                        except:
                            dup += 1
                    conn.commit()
                    st.success(f"导入完成！\n有效码总数：{len(codes)}\n成功导入：{ok}个\n重复跳过：{dup}个")
                    with st.expander("查看解析到的Boss码", expanded=False):
                        st.code("\n".join(codes), language="text")

            st.divider()

            # 2. 手动粘贴导入
            st.subheader("📝 手动粘贴导入Boss码（空格分隔）")
            st.caption("支持格式：xxxxx xxxxx xxxxx（空格分隔）、一行一个、换行+空格混合，自动过滤无效码、自动去重")
            code_input = st.text_area("粘贴Boss码内容", height=200, key="paste_code_input")
            if st.button("批量导入粘贴的码", use_container_width=True, key="paste_import_btn"):
                if not code_input.strip():
                    st.warning("请粘贴Boss码内容")
                else:
                    codes = parse_boss_codes(code_input)
                    if not codes:
                        st.error("未解析到有效Boss码（仅支持5位字母/数字组合）")
                    else:
                        ok = 0
                        dup = 0
                        for cd in codes:
                            try:
                                c.execute("INSERT INTO boss_codes (code) VALUES (?)", (cd,))
                                ok += 1
                            except:
                                dup += 1
                        conn.commit()
                        st.success(f"导入完成！\n有效码总数：{len(codes)}\n成功导入：{ok}个\n重复跳过：{dup}个")
                        with st.expander("查看解析到的Boss码", expanded=False):
                            st.code("\n".join(codes), language="text")

            st.divider()

            # 3. Boss码删除管理
            st.subheader("🗑️ Boss码删除管理")
            del_type = st.radio("选择删除方式", ["单个删除", "批量删除（按ID范围）"], horizontal=True, key="code_del_type")
            if del_type == "单个删除":
                col1, col2 = st.columns(2)
                with col1:
                    did = st.number_input("要删除的Boss码ID", min_value=1, step=1, key="code_del_id")
                with col2:
                    confirm_del = st.checkbox("确认删除（不可恢复）", key="code_del_confirm")
                if confirm_del and st.button("执行单个删除", key="code_del_btn"):
                    c.execute("SELECT code FROM boss_codes WHERE id=?", (did,))
                    r = c.fetchone()
                    if not r:
                        st.error("该ID的Boss码不存在！")
                    else:
                        c.execute("DELETE FROM receive_records WHERE code_id=?", (did,))
                        c.execute("DELETE FROM boss_codes WHERE id=?", (did,))
                        conn.commit()
                        st.success(f"成功删除Boss码：{r[0]}（ID：{did}）")
            else:
                col1, col2, col3 = st.columns(3)
                with col1:
                    s = st.number_input("起始ID", min_value=1, key="code_batch_del_start")
                with col2:
                    e = st.number_input("结束ID", min_value=1, key="code_batch_del_end")
                with col3:
                    confirm_batch_del = st.checkbox("确认批量删除（不可恢复）", key="code_batch_del_confirm")
                if confirm_batch_del and st.button("执行批量删除", key="code_batch_del_btn"):
                    if s > e:
                        st.error("起始ID不能大于结束ID！")
                    else:
                        c.execute("SELECT COUNT(*) FROM boss_codes WHERE id BETWEEN ? AND ?", (s, e))
                        count = c.fetchone()[0]
                        if count == 0:
                            st.error("该ID范围内无Boss码！")
                        else:
                            c.execute("DELETE FROM receive_records WHERE code_id BETWEEN ? AND ?", (s, e))
                            c.execute("DELETE FROM boss_codes WHERE id BETWEEN ? AND ?", (s, e))
                            conn.commit()
                            st.success(f"批量删除完成！共删除 {count} 个Boss码")

            st.divider()

            # 4. Boss码库存列表
            st.subheader("Boss码库存列表")
            t = st.selectbox("筛选状态", ["全部", "未领取", "已领取"], key="code_list_filter")
            if t == "未领取":
                c.execute("SELECT * FROM boss_codes WHERE is_used=0 ORDER BY id DESC")
            elif t == "已领取":
                c.execute("SELECT * FROM boss_codes WHERE is_used=1 ORDER BY receive_time DESC")
            else:
                c.execute("SELECT * FROM boss_codes ORDER BY id DESC")
            st.dataframe(c.fetchall(), use_container_width=True, key="code_list_df")

        # ========== 用户管理（优化密码重置，支持用户名） ==========
        with tabs[1]:
            st.subheader("用户列表")
            c.execute("SELECT id, username, permission_level, remain_receive_times, create_time FROM users ORDER BY id DESC")
            users = c.fetchall()
            st.dataframe(users, use_container_width=True, key="user_list_df")

            # 管理员重置用户密码（优化版，支持用户名/ID）
            if st.session_state.permission_level >= 1:
                st.divider()
                st.subheader("🔐 管理员重置用户密码")
                reset_method = st.radio("选择重置方式", ["按用户名重置", "按用户ID重置"], horizontal=True, key="admin_reset_method")
                
                if reset_method == "按用户名重置":
                    reset_uname = st.text_input("要重置的用户名", key="admin_reset_uname")
                    admin_new_pwd = st.text_input("设置新密码", type="password", key="admin_reset_pwd")
                    if st.button("执行重置", type="primary", use_container_width=True, key="admin_reset_uname_btn"):
                        if not reset_uname.strip():
                            st.error("请输入用户名")
                        elif len(admin_new_pwd) < 6:
                            st.error("密码至少6位")
                        else:
                            c.execute("SELECT id, username, permission_level FROM users WHERE username = ?", (reset_uname,))
                            u = c.fetchone()
                            if not u:
                                st.error("该用户名不存在！")
                            elif u[2] == PERMISSION_SUPER_ADMIN and st.session_state.permission_level != PERMISSION_SUPER_ADMIN:
                                st.error("次级管理员无权修改超级管理员的密码")
                            else:
                                c.execute("UPDATE users SET password = ? WHERE username = ?", (admin_new_pwd, reset_uname))
                                conn.commit()
                                st.success(f"用户【{reset_uname}】的密码已重置成功！")
                else:
                    reset_uid = st.number_input("要重置的用户ID", min_value=1, step=1, key="admin_reset_uid")
                    admin_new_pwd = st.text_input("设置新密码", type="password", key="admin_reset_pwd_id")
                    if st.button("执行重置", type="primary", use_container_width=True, key="admin_reset_uid_btn"):
                        if len(admin_new_pwd) < 6:
                            st.error("密码至少6位")
                        else:
                            c.execute("SELECT id, username, permission_level FROM users WHERE id = ?", (reset_uid,))
                            u = c.fetchone()
                            if not u:
                                st.error("该ID的用户不存在！")
                            elif u[2] == PERMISSION_SUPER_ADMIN and st.session_state.permission_level != PERMISSION_SUPER_ADMIN:
                                st.error("次级管理员无权修改超级管理员的密码")
                            else:
                                c.execute("UPDATE users SET password = ? WHERE id = ?", (admin_new_pwd, reset_uid))
                                conn.commit()
                                st.success(f"用户【{u[1]}】的密码已重置成功！")

            st.divider()
            st.subheader("🔄 重置用户领取次数")
            reset_type = st.radio("选择重置方式", ["单个用户重置", "批量用户重置（按ID范围）"], horizontal=True, key="reset_type")
            
            if reset_type == "单个用户重置":
                col1, col2 = st.columns(2)
                with col1:
                    reset_uid = st.number_input("要重置的用户ID", min_value=1, step=1, key="reset_uid")
                with col2:
                    reset_times = st.number_input("重置为多少次", min_value=0, step=1, value=10, key="reset_times")
                if st.button("执行单个重置", type="primary", use_container_width=True, key="reset_single_btn"):
                    c.execute("SELECT username FROM users WHERE id=?", (reset_uid,))
                    u = c.fetchone()
                    if not u:
                        st.error("该ID的用户不存在！")
                    else:
                        c.execute("UPDATE users SET remain_receive_times=? WHERE id=?", (reset_times, reset_uid))
                        conn.commit()
                        st.success(f"成功重置用户【{u[0]}】的领取次数为 {reset_times} 次！")
            else:
                col1, col2, col3 = st.columns(3)
                with col1:
                    reset_start_id = st.number_input("起始用户ID", min_value=1, step=1, value=1, key="reset_start_id")
                with col2:
                    reset_end_id = st.number_input("结束用户ID", min_value=1, step=1, value=10, key="reset_end_id")
                with col3:
                    reset_batch_times = st.number_input("重置为多少次", min_value=0, step=1, value=10, key="reset_batch_times")
                if st.button("执行批量重置", type="primary", use_container_width=True, key="reset_batch_btn"):
                    if reset_start_id > reset_end_id:
                        st.error("起始ID不能大于结束ID！")
                    else:
                        c.execute("""
                            UPDATE users 
                            SET remain_receive_times=? 
                            WHERE id BETWEEN ? AND ? AND permission_level != ?
                        """, (reset_batch_times, reset_start_id, reset_end_id, PERMISSION_SUPER_ADMIN))
                        affected = conn.total_changes
                        conn.commit()
                        st.success(f"批量重置完成！共重置 {affected} 个用户的领取次数为 {reset_batch_times} 次")

            st.divider()
            st.subheader("🗑️ 用户删除管理（仅超管）")
            if st.session_state.permission_level == 2:
                del_u_type = st.radio("选择用户删除方式", ["单个删除用户", "批量删除用户（按ID范围）"], horizontal=True, key="user_del_type")
                if del_u_type == "单个删除用户":
                    col1, col2 = st.columns(2)
                    with col1:
                        duid = st.number_input("要删除的用户ID", min_value=1, step=1, key="user_del_id")
                    with col2:
                        confirm_user_del = st.checkbox("我确认要删除该用户（不可恢复）", key="user_del_confirm")
                    if confirm_user_del and st.button("执行单个删除用户", key="user_del_btn"):
                        if duid == st.session_state.user_id:
                            st.error("不能删除自己的账号！")
                        else:
                            c.execute("SELECT username, permission_level FROM users WHERE id=?", (duid,))
                            u = c.fetchone()
                            if not u:
                                st.error("该ID的用户不存在！")
                            elif u[1] == 2:
                                st.error("不能删除超级管理员账号！")
                            else:
                                c.execute("DELETE FROM receive_records WHERE user_id=?", (duid,))
                                c.execute("DELETE FROM users WHERE id=?", (duid,))
                                conn.commit()
                                st.success(f"成功删除用户：{u[0]}（ID：{duid}），并清理了其所有领取记录")
                else:
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        delete_user_start_id = st.number_input("起始用户ID", min_value=1, step=1, value=1, key="user_batch_del_start")
                    with col2:
                        delete_user_end_id = st.number_input("结束用户ID", min_value=1, step=1, value=10, key="user_batch_del_end")
                    with col3:
                        confirm_batch_user_delete = st.checkbox("确认批量删除（不可恢复）", key="user_batch_del_confirm")
                    if confirm_batch_user_delete and st.button("执行批量删除用户", key="user_batch_del_btn"):
                        if delete_user_start_id > delete_user_end_id:
                            st.error("起始ID不能大于结束ID！")
                        elif delete_user_start_id <= st.session_state.user_id <= delete_user_end_id:
                            st.error("不能删除包含自己账号的ID范围！")
                        else:
                            c.execute("""
                                SELECT COUNT(*) FROM users 
                                WHERE id BETWEEN ? AND ? 
                                AND permission_level != ?
                            """, (delete_user_start_id, delete_user_end_id, PERMISSION_SUPER_ADMIN))
                            count = c.fetchone()[0]
                            if count == 0:
                                st.error("该ID范围内无普通用户/次级管理员可删除！")
                            else:
                                c.execute("DELETE FROM receive_records WHERE user_id BETWEEN ? AND ?", (delete_user_start_id, delete_user_end_id))
                                c.execute("""
                                    DELETE FROM users 
                                    WHERE id BETWEEN ? AND ? 
                                    AND permission_level != ?
                                """, (delete_user_start_id, delete_user_end_id, PERMISSION_SUPER_ADMIN))
                                conn.commit()
                                st.success(f"批量删除完成！共删除 {count} 个用户，并清理了其所有领取记录")

            st.divider()
            st.subheader("📊 批量设置用户领取次数")
            batch_type = st.radio("选择批量方式", ["按用户ID范围", "按用户ID列表"], horizontal=True, key="batch_times_type")
            if batch_type == "按用户ID范围":
                col1, col2, col3 = st.columns(3)
                with col1:
                    start_id = st.number_input("起始用户ID", min_value=1, step=1, value=1, key="batch_times_start")
                with col2:
                    end_id = st.number_input("结束用户ID", min_value=1, step=1, value=10, key="batch_times_end")
                with col3:
                    batch_remain_times = st.number_input("批量设置次数", min_value=0, step=1, value=1, key="batch_times_num")
                if st.button("执行批量设置（ID范围）", type="primary", use_container_width=True, key="batch_times_range_btn"):
                    if start_id > end_id:
                        st.error("起始ID不能大于结束ID")
                    else:
                        c.execute("""
                            UPDATE users 
                            SET remain_receive_times = ? 
                            WHERE id BETWEEN ? AND ? AND permission_level != ?
                        """, (batch_remain_times, start_id, end_id, PERMISSION_SUPER_ADMIN))
                        affected = conn.total_changes
                        conn.commit()
                        st.success(f"批量设置完成！共修改 {affected} 个用户的领取次数")
            else:
                id_list_input = st.text_area("输入用户ID（多个用英文逗号/换行分隔）", placeholder="例如：1,3,5 或每行一个ID", key="batch_times_id_list")
                col1, col2 = st.columns(2)
                with col1:
                    batch_remain_times = st.number_input("批量设置次数", min_value=0, step=1, value=1, key="batch_times_list_num")
                if st.button("执行批量设置（ID列表）", type="primary", use_container_width=True, key="batch_times_list_btn"):
                    if not id_list_input.strip():
                        st.error("请输入用户ID列表")
                    else:
                        id_list = []
                        lines = id_list_input.split("\n")
                        for line in lines:
                            ids = line.split(",")
                            for id_str in ids:
                                id_str = id_str.strip()
                                if id_str.isdigit():
                                    id_list.append(int(id_str))
                        if not id_list:
                            st.error("未识别到有效用户ID")
                        else:
                            id_placeholders = ",".join(["?"] * len(id_list))
                            c.execute(f"""
                                UPDATE users 
                                SET remain_receive_times = ? 
                                WHERE id IN ({id_placeholders}) AND permission_level != ?
                            """, [batch_remain_times] + id_list + [PERMISSION_SUPER_ADMIN])
                            affected = conn.total_changes
                            conn.commit()
                            st.success(f"批量设置完成！共修改 {affected} 个用户的领取次数")

        # ========== 领取记录 ==========
        with tabs[2]:
            st.subheader("全量领取记录")
            c.execute('''
                SELECT r.id, u.username, r.code, r.receive_time 
                FROM receive_records r
                LEFT JOIN users u ON r.user_id = u.id
                ORDER BY r.receive_time DESC
            ''')
            st.dataframe(c.fetchall(), use_container_width=True, key="record_list_df")

        # ========== 库存统计 ==========
        with tabs[3]:
            c.execute("SELECT COUNT(*) FROM boss_codes")
            total = c.fetchone()[0]
            c.execute("SELECT COUNT(*) FROM boss_codes WHERE is_used=0")
            rem = c.fetchone()[0]
            c.execute("SELECT COUNT(*) FROM boss_codes WHERE is_used=1")
            used = c.fetchone()[0]
            col1, col2, col3 = st.columns(3)
            col1.metric("总库存", total)
            col2.metric("剩余可领取", rem)
            col3.metric("已领取", used)

        # ========== 权限设置 ==========
        if len(tabs) >= 5:
            with tabs[4]:
                st.subheader("🔐 次级管理员权限设置")
                target_user_id = st.number_input("目标用户ID", min_value=1, step=1, key="perm_modify_uid")
                target_permission = st.selectbox(
                    "设置用户权限",
                    options=[("普通用户", PERMISSION_USER), ("次级管理员", PERMISSION_SUB_ADMIN)],
                    format_func=lambda x: x[0],
                    key="perm_modify_level"
                )
                if st.button("确认修改权限", type="primary", use_container_width=True, key="perm_modify_btn"):
                    if target_user_id == st.session_state.user_id:
                        st.error("不可修改自己的权限")
                    else:
                        c.execute("SELECT username FROM users WHERE id = ?", (target_user_id,))
                        target_user = c.fetchone()
                        if not target_user:
                            st.error("目标用户不存在")
                        else:
                            c.execute("UPDATE users SET permission_level = ? WHERE id = ?", (target_permission[1], target_user_id))
                            conn.commit()
                            st.success(f"用户【{target_user[0]}】的权限已修改为【{target_permission[0]}】")
                
                st.divider()
                st.subheader("当前管理员列表")
                c.execute("SELECT id, username, permission_level, create_time FROM users WHERE permission_level >= 1 ORDER BY permission_level DESC")
                admin_list = c.fetchall()
                admin_data = []
                for admin in admin_list:
                    role = "超级管理员" if admin[2] == PERMISSION_SUPER_ADMIN else "次级管理员"
                    admin_data.append([admin[0], admin[1], role, admin[3]])
                st.dataframe(admin_data, use_container_width=True, key="admin_list_df")

    # ========== 普通用户领码界面 ==========
    st.header("🎁 Boss码自助领取")
    c.execute("SELECT remain_receive_times FROM users WHERE id=?", (st.session_state.user_id,))
    rt = c.fetchone()[0]
    st.metric("剩余可领取次数", rt)

    if st.button("一次性领取所有Boss码", type="primary", use_container_width=True, disabled=rt <= 0, key="receive_all_btn"):
        # 先查库存
        c.execute("SELECT id, code FROM boss_codes WHERE is_used = 0")
        available_codes = c.fetchall()
        
        if not available_codes:
            st.error("当前Boss码已领完，请联系管理员补充库存")
        elif len(available_codes) < rt:
            st.warning(f"库存不足！当前仅剩 {len(available_codes)} 个码，已为你全部领取")
            num_to_receive = len(available_codes)
        else:
            num_to_receive = rt
        
        # 开始领取
        if num_to_receive > 0:
            # 随机选码
            selected_codes = random.sample(available_codes, num_to_receive)
            received_code_list = []
            
            for code_info in selected_codes:
                code_id = code_info[0]
                code = code_info[1]
                
                # 更新码状态
                c.execute("UPDATE boss_codes SET is_used = 1, receive_user_id = ?, receive_time = ? WHERE id = ?",
                          (st.session_state.user_id, datetime.now(), code_id))
                # 插入领取记录
                c.execute("INSERT INTO receive_records (user_id, code_id, code) VALUES (?, ?, ?)",
                          (st.session_state.user_id, code_id, code))
                received_code_list.append(code)
            
            # 更新用户剩余次数
            c.execute("UPDATE users SET remain_receive_times = remain_receive_times - ? WHERE id = ?", (num_to_receive, st.session_state.user_id))
            conn.commit()
            
            # 显示结果
            st.success(f"领取成功！共领取 {len(received_code_list)} 个Boss码：")
            for i, code in enumerate(received_code_list, 1):
                st.code(f"{i}. {code}", language="text")
            st.warning("请妥善保管，每个码仅可使用一次")
    
    st.divider()
    st.subheader("我的领取记录")
    c.execute("SELECT code, receive_time FROM receive_records WHERE user_id = ? ORDER BY receive_time DESC", (st.session_state.user_id,))
    my_records = c.fetchall()
    if my_records:
        st.dataframe(my_records, use_container_width=True, key="my_record_df")
    else:
        st.info("你还没有领取过Boss码")
