import streamlit as st
import requests
import json
import re
from bs4 import BeautifulSoup
import time
import os
from datetime import datetime
import glob

# 设置页面配置 - 必须是第一个 Streamlit 命令
st.set_page_config(
    page_title="开源项目资讯",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items=None
)

# 加载自定义CSS
with open('.streamlit/style.css') as f:
    st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)

# 创建文章保存目录
ARTICLES_DIR = "articles"
if not os.path.exists(ARTICLES_DIR):
    os.makedirs(ARTICLES_DIR)

def extract_github_info(text):
    """从API响应中提取GitHub项目信息"""
    try:
        data = json.loads(text)
        return data.get('projects', []), data.get('companies', []), data.get('news_title', ''), data.get('news_content', '')
    except:
        return [], [], '', ''

def clean_repo_name(name):
    """清理仓库名称，移除特殊字符"""
    # 移除空格和特殊字符
    name = re.sub(r'[^\w\-./]', '', name)
    return name

def search_github_api(query):
    """使用GitHub API搜索仓库"""
    try:
        # 使用GitHub API搜索
        github_token = st.secrets.get("GITHUB_TOKEN", "")
        headers = {
            'Authorization': f'token {github_token}',
            'Accept': 'application/vnd.github.v3+json'
        }
        # 按照stars数量排序，获取最相关的结果
        search_url = f"https://api.github.com/search/repositories?q={query}&sort=stars&order=desc"
        response = requests.get(search_url, headers=headers)
        
        if response.status_code == 200:
            data = response.json()
            if data['items']:
                repo = data['items'][0]  # 获取第一个结果
                return {
                    'stars': str(repo['stargazers_count']),
                    'forks': str(repo['forks_count']),
                    'url': repo['html_url'],
                    'full_name': repo['full_name']
                }
    except Exception as e:
        st.error(f"GitHub API搜索出错: {str(e)}")
    return None

def get_github_stats(repo_name):
    """获取GitHub仓库的star和fork数量"""
    try:
        # 清理仓库名称
        repo_name = repo_name.strip()
        
        # 处理特殊情况
        if repo_name.lower() == "deepseek r1":
            repo_name = "deepseek-ai/deepseek-coder"
        
        # 尝试直接访问仓库页面
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        
        # 如果是完整的仓库名（包含/），直接使用
        if '/' not in repo_name:
            # 对于 ollama 这样的项目，添加组织名
            if repo_name.lower() == 'ollama':
                repo_name = 'ollama/ollama'
        
        direct_url = f"https://github.com/{repo_name}"
        response = requests.get(direct_url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 获取star数量 - 更新选择器
            stars = '0'
            star_element = soup.select_one('a[href$="/stargazers"] > strong')
            if star_element:
                stars = star_element.text.strip()
            
            # 获取fork数量 - 更新选择器
            forks = '0'
            fork_element = soup.select_one('a[href$="/forks"] > strong')
            if fork_element:
                forks = fork_element.text.strip()
            
            # 如果找到数据，返回结果
            if stars != '0' or forks != '0':
                # 移除千分位逗号
                stars = stars.replace(',', '')
                forks = forks.replace(',', '')
                return {
                    'stars': stars,
                    'forks': forks,
                    'url': direct_url
                }
        
        # 如果直接访问失败，尝试搜索
        search_url = f"https://github.com/search?q={repo_name}&type=repositories"
        response = requests.get(search_url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            repo_link = soup.select_one('.search-title a:first-child')
            
            if repo_link:
                repo_url = "https://github.com" + repo_link['href']
                response = requests.get(repo_url, headers=headers, timeout=10)
                
                if response.status_code == 200:
                    soup = BeautifulSoup(response.text, 'html.parser')
                    
                    # 获取star数量
                    stars = '0'
                    star_element = soup.select_one('a[href$="/stargazers"] > strong')
                    if star_element:
                        stars = star_element.text.strip().replace(',', '')
                    
                    # 获取fork数量
                    forks = '0'
                    fork_element = soup.select_one('a[href$="/forks"] > strong')
                    if fork_element:
                        forks = fork_element.text.strip().replace(',', '')
                    
                    if stars != '0' or forks != '0':
                        return {
                            'stars': stars,
                            'forks': forks,
                            'url': repo_url
                        }
        
        return {
            'stars': '数据未找到',
            'forks': '数据未找到',
            'url': f'https://github.com/search?q={repo_name}'
        }
            
    except Exception as e:
        st.error(f"获取GitHub数据时出错: {str(e)}")
        return {
            'stars': '获取失败',
            'forks': '获取失败',
            'url': f'https://github.com/search?q={repo_name}'
        }

def analyze_content(text):
    """调用API分析内容"""
    url = "https://api.siliconflow.cn/v1/chat/completions"
    headers = {
        "Authorization": "Bearer sk-ydcvskcyyzictsylxplbpqmqlpillcpkqznxclfjyohkefwt",
        "Content-Type": "application/json"
    }
    
    formatted_prompt = f"""请分析下面的文本，提取以下信息：
    1. 提到的开源项目名称
    2. 提到的公司名称
    3. 将文本重写为一篇资讯报道（包含标题和内容）
    
    文本内容：{text}
    
    请以JSON格式返回，格式如下：
    {{
        "projects": ["仓库名1", "仓库名2"],
        "companies": ["公司1", "公司2"],
        "news_title": "新闻标题",
        "news_content": "新闻内容"
    }}"""

    payload = {
        "model": "Qwen/Qwen2.5-72B-Instruct-128K",
        "messages": [{"role": "user", "content": formatted_prompt}],
        "stream": False,
        "max_tokens": 2048,
        "stop": ["<string>"],
        "temperature": 0.7,
        "top_p": 0.7,
        "top_k": 50,
        "frequency_penalty": 0.5,
        "n": 1,
        "response_format": {"type": "json_object"}
    }

    response = requests.post(url, json=payload, headers=headers)
    if response.status_code == 200:
        data = response.json()
        return data['choices'][0]['message']['content'].strip()
    else:
        st.error(f"Error: {response.status_code} - {response.text}")
        return None

def save_article(title, content, projects, companies):
    """保存文章为Markdown文件"""
    # 生成文件名
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{timestamp}_{title[:30]}.md"
    filepath = os.path.join(ARTICLES_DIR, filename)
    
    # 构建Markdown内容
    markdown_content = f"""# {title}

##### 相关项目
"""
    
    # 添加项目信息
    for project in projects:
        stats = get_github_stats(project)
        markdown_content += f"- [{project}]({stats['url']}) - ⭐ {stats['stars']} | 🔄 {stats['forks']}\n"
    
    # 添加公司信息
    if companies:
        markdown_content += "\n##### 相关公司\n"
        for company in companies:
            markdown_content += f"- {company}\n"
    
    # 添加正文
    markdown_content += f"\n{content}\n"
    
    # 保存文件
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(markdown_content)
    
    return filename

def list_articles():
    """获取所有文章列表"""
    articles = []
    for file in glob.glob(os.path.join(ARTICLES_DIR, "*.md")):
        filename = os.path.basename(file)
        # 从文件名中提取时间和标题
        time_str = filename[:15]  # 获取时间戳部分
        title = filename[16:-3]   # 获取标题部分（去掉.md）
        
        # 读取文件内容获取第一行作为标题
        with open(file, 'r', encoding='utf-8') as f:
            full_title = f.readline().strip('# \n')
        
        created_time = datetime.strptime(time_str, "%Y%m%d_%H%M%S")
        articles.append({
            'filename': filename,
            'title': full_title,
            'created_time': created_time,
            'path': file
        })
    
    # 按时间倒序排序
    return sorted(articles, key=lambda x: x['created_time'], reverse=True)

def main():
    # 创建侧边栏导航
    with st.sidebar:
        st.markdown('<div class="sidebar-title">📝 导航菜单</div>', unsafe_allow_html=True)
        
        # 导航选项
        nav_items = {
            "✨ 创建新文章": "create",
            "📚 全部文章": "list"
        }
        
        # 使用session_state来保持导航状态
        if 'nav' not in st.session_state:
            st.session_state.nav = 'create'
            
        for label, value in nav_items.items():
            if st.button(label, key=f"nav_{value}", use_container_width=True):
                st.session_state.nav = value
    
    # 根据导航选择显示不同内容
    if st.session_state.nav == "create":
        st.markdown('<h1 class="main-title">✨ 创建新文章</h1>', unsafe_allow_html=True)
        text = st.text_area("输入要分析的文本内容:", height=200)
        col1, col2, col3 = st.columns([1,1,1])
        with col2:
            analyze_button = st.button("🔍 开始AI重写整理", use_container_width=True)
        
        if analyze_button and text:
            with st.spinner("🔄 正在分析内容..."):
                result = analyze_content(text)
                if result:
                    projects, companies, news_title, news_content = extract_github_info(result)
                    
                    # 显示生成的新闻
                    if news_title and news_content:
                        st.markdown(f'''
                        <div class="article-card">
                            <h2 class="article-title">{news_title}</h2>
                            <div class="article-meta">
                                <span class="meta-item">📅 {datetime.now().strftime("%Y-%m-%d %H:%M")}</span>
                                <span class="meta-item">👀 开源项目: {len(projects)}个</span>
                                <span class="meta-item">🏢 相关公司: {len(companies)}个</span>
                            </div>
                            <div class="article-content">{news_content}</div>
                        </div>
                        ''', unsafe_allow_html=True)
                    
                    # 显示项目信息（表格形式）
                    if projects:
                        st.markdown('<div class="section-title">📦 相关开源项目</div>', unsafe_allow_html=True)
                        table_rows = []
                        for project in projects:
                            stats = get_github_stats(project)
                            table_rows.append(f'''
                            <tr>
                                <td><a href="{stats['url']}" target="_blank">{project}</a></td>
                                <td>
                                    <div class="project-stats">
                                        <span class="stat-item">⭐ {stats['stars']}</span>
                                        <span class="stat-item">🔄 {stats['forks']}</span>
                                    </div>
                                </td>
                            </tr>
                            ''')
                        
                        st.markdown(f'''
                        <table class="project-table">
                            <thead>
                                <tr>
                                    <th>项目名称</th>
                                    <th>统计信息</th>
                                </tr>
                            </thead>
                            <tbody>
                                {"".join(table_rows)}
                            </tbody>
                        </table>
                        ''', unsafe_allow_html=True)
                    
                    # 显示公司标签
                    if companies:
                        st.markdown('<div class="section-title">🏢 相关公司</div>', unsafe_allow_html=True)
                        tags_html = ''.join([f'<span class="company-tag">🏢 {company}</span>' for company in companies])
                        st.markdown(f'<div class="company-tags">{tags_html}</div>', unsafe_allow_html=True)
                    
                    # 保存文章
                    filename = save_article(news_title, news_content, projects, companies)
                    st.success(f"✅ 文章已保存: {filename}")
    
    else:  # st.session_state.nav == "list"
        st.markdown('<h1 class="main-title">📚 全部文章</h1>', unsafe_allow_html=True)
        articles = list_articles()
        
        if articles:
            # 文章过滤和搜索（可选功能）
            search = st.text_input("🔍 搜索文章", "")
            
            filtered_articles = articles
            if search:
                filtered_articles = [
                    article for article in articles 
                    if search.lower() in article['title'].lower()
                ]
            
            # 显示文章列表
            for article in filtered_articles:
                # 读取文章内容
                with open(article['path'], 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # 显示文章卡片
                st.markdown(f'''
                <div class="article-card">
                    <h2 class="article-title">{article['title']}</h2>
                    <div class="article-meta">
                        <span class="meta-item">📅 发布于: {article["created_time"].strftime("%Y-%m-%d %H:%M")}</span>
                    </div>
                    <div class="article-content">{content}</div>
                </div>
                ''', unsafe_allow_html=True)
        else:
            st.info('📝 还没有保存的文章，点击"创建新文章"开始写作吧！')

if __name__ == "__main__":
    main()
