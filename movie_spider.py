import aiofiles
import asyncio
import aiohttp
import requests
from lxml import etree
import re
import os
from urllib.parse import urljoin
import subprocess

# 请求头，模拟浏览器访问，避免被反爬
headers = {
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "accept-language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
    "cache-control": "no-cache",
    "pragma": "no-cache",
    "priority": "u=0, i",
    "referer": "https://www.langfangshuzhi.com/vod/3258.html",
    "sec-ch-ua": "\"Not:A-Brand\";v=\"99\", \"Microsoft Edge\";v=\"145\", \"Chromium\";v=\"145\"",
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": "\"Windows\"",
    "sec-fetch-dest": "document",
    "sec-fetch-mode": "navigate",
    "sec-fetch-site": "same-origin",
    "sec-fetch-user": "?1",
    "upgrade-insecure-requests": "1",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36 Edg/145.0.0.0"
}

def get_m3u8_url(url):
    """
    从视频播放页面提取真实的 m3u8 地址和视频标题。
    通过解析页面中 <script> 标签内的 JSON 数据获取。
    :param url: 视频播放页面的 URL
    :return: 字典，包含 'title'（视频标题）和 'm3u8_url'（m3u8 文件地址）
    """
    res = requests.get(url, headers=headers)
    html = etree.HTML(res.text)
    # 获取所有 type="text/javascript" 的 script 标签内容
    url_tags = html.xpath('//script[@type="text/javascript"]/text()')
    url_tag = ','.join(url_tags)  # 合并为一个大字符串
    # 使用正则提取 "url":"..." 中的地址
    m3u8_url = re.search(r'"url":"(.*?)","url_next"', url_tag).group(1)
    m3u8_url = m3u8_url.replace('\\', '')  # 去除可能存在的转义反斜杠
    # 提取标题
    title = html.xpath('//h3[@class="title text-fff"]/text()')[0].strip()
    return {'title': title, 'm3u8_url': m3u8_url}

def parse_m3u8_url(m3u8_url, file_path, file_name):
    """
    下载指定 URL 的 m3u8 文件并保存到本地。
    :param m3u8_url: m3u8 文件的 URL
    :param file_path: 本地保存目录
    :param file_name: 保存的文件名
    """
    res = requests.get(m3u8_url, headers=headers)
    # 如果目录不存在则创建
    os.path.exists(file_path) or os.makedirs(file_path)
    with open(f'{file_path}/{file_name}', 'w', encoding='utf-8') as f:
        f.write(res.text)

def confirm_m3u8(full_file_path, m3u8_url):
    """
    检查当前 m3u8 文件是否为多级索引（包含 #EXT-X-STREAM-INF 标签）。
    如果是，则返回下一级 m3u8 的完整 URL；否则返回 False。
    :param full_file_path: 已保存的 m3u8 文件路径
    :param m3u8_url: 当前 m3u8 文件的基准 URL（用于拼接相对路径）
    :return: 下一级 m3u8 的 URL 或 False
    """
    with open(full_file_path, 'r', encoding='utf-8') as f:
        for line in f:
            if line.startswith('#EXT-X-STREAM-INF'):
                url = f.readline().strip()  # 读取下一行，即真正的 m3u8 地址
                if url.startswith('http'):
                    m3u8_url = url
                else:
                    # 拼接相对路径
                    m3u8_url = urljoin(m3u8_url, url)
                return m3u8_url
        return False

def download_key(url, file_path):
    """
    下载 AES-128 加密所需的密钥文件（enc.key）。
    :param url: 密钥文件的 URL
    :param file_path: 本地保存目录
    """
    res = requests.get(url, headers=headers)
    with open(f'{file_path}/enc.key', 'wb') as f:
        f.write(res.content)

def create_tasks(full_file_path, m3u8_url):
    """
    从最终的 m3u8 文件中提取所有 TS 片段的 URL（或相对路径），并转换为完整 URL。
    :param full_file_path: 最终的 m3u8 文件路径
    :param m3u8_url: 该 m3u8 文件的基准 URL，用于拼接
    :return: 包含所有 TS 片段完整 URL 的列表
    """
    with open(full_file_path, 'r', encoding='utf-8') as f:
        tasks_urls = []
        for line in f:
            if not line.startswith('#'):  # 忽略注释行
                line = line.strip()
                if line.startswith('http'):
                    tasks_urls.append(line)
                else:
                    # 拼接相对路径
                    full_url = urljoin(m3u8_url, line)
                    tasks_urls.append(full_url)
        return tasks_urls

async def download_tasks(tasks_urls, file_path):
    """
    并发下载所有 TS 片段。
    :param tasks_urls: TS 片段的 URL 列表
    :param file_path: 本地保存目录
    """
    sem = asyncio.Semaphore(100)  # 控制最大并发数，防止系统资源耗尽
    tasks = []
    for task_url in tasks_urls:
        tasks.append(asyncio.create_task(download_file(task_url, file_path, sem)))
    await asyncio.gather(*tasks)
    print('下载完成')

async def download_file(url, file_path, sem):
    """
    下载单个 TS 文件，支持重试。
    :param url: TS 文件的 URL
    :param file_path: 本地保存目录
    :param sem: 信号量，用于控制并发
    """
    file_name = url.split('/')[-1]
    # 强制将扩展名改为 .ts（有时原文件可能无后缀或后缀不对）
    file_name = file_name.replace(file_name.split('.')[-1], 'ts')
    tm = aiohttp.ClientTimeout(total=10)  # 每个请求超时 10 秒
    async with sem:  # 获取信号量
        while True:
            try:
                # 异步写入文件
                async with aiofiles.open(f'{file_path}/{file_name}', 'wb') as f:
                    async with aiohttp.ClientSession(timeout=tm) as session:
                        async with session.get(url, headers=headers) as response:
                            chunk = await response.content.read()
                            await f.write(chunk)
                            print(f'下载完成{file_name}')
                            break  # 成功则退出重试循环
            except Exception as e:
                print(f'重试下载{file_name}')  # 失败后打印信息并继续重试

def re_write_m3u8(file_path, file_name):
    """
    将本地的 m3u8 文件重写为仅包含 TS 文件名（去除路径部分），以便 ffmpeg 能正确找到本地文件。
    :param file_path: 文件所在目录
    :param file_name: 原始 m3u8 文件名
    :return: 新生成的文件名（local_原文件名）
    """
    with open(f'{file_path}/{file_name}', 'r', encoding='utf-8') as f1, \
         open(f'{file_path}/local_{file_name}', 'w', encoding='utf-8') as f2:
        for line in f1:
            if line.startswith('#'):
                f2.write(line)  # 保留所有注释行
            else:
                # 提取 URL 中的文件名部分（即最后一个 '/' 之后的内容）
                data = line.split('/')[-1]
                f2.write(data)
    return f'local_{file_name}'

def merge_video(file_path, m3u8, title):
    """
    调用 ffmpeg 将本地 TS 片段合并为完整的 MP4 文件。
    :param file_path: 文件所在目录
    :param m3u8: 重写后的 m3u8 文件名（local_xxx.m3u8）
    :param title: 视频标题，用于输出文件名
    :return: True 表示合并成功，False 表示失败
    """
    input_file = f'{file_path}/{m3u8}'
    output_file = f'{file_path}/{title}.mp4'
    # 构建 ffmpeg 命令：-allowed_extensions ALL 允许加载 .key 等非多媒体文件
    cmd = f'ffmpeg -allowed_extensions ALL -i {input_file} -c copy {output_file}'
    try:
        subprocess.run(cmd, check=True)  # 执行命令，check=True 会在失败时抛出异常
        print(f'合并完成{title}.mp4')
        return True
    except Exception as e:
        print(f'合并失败{title}.mp4')
        return False

def remove_files(file_path):
    """
    删除指定目录下所有 .ts、.key 和 .m3u8 文件（清理临时文件）。
    :param file_path: 目标目录
    """
    for file in os.listdir(file_path):
        if file.endswith('.ts'):
            os.remove(f'{file_path}/{file}')
        elif file.endswith('.key'):
            os.remove(f'{file_path}/{file}')
        elif file.endswith('.m3u8'):
            os.remove(f'{file_path}/{file}')
    print('文件清理完成')

async def main():
    """
    主流程：
    1. 从播放页获取真实 m3u8 地址和标题
    2. 下载初始 m3u8 文件
    3. 下载密钥文件（如果存在）
    4. 循环处理多级 m3u8，直到得到最终的 ts 列表文件
    5. 提取所有 ts 片段的 URL
    6. 并发下载所有 ts 片段
    7. 重写 m3u8 为本地相对路径
    8. 调用 ffmpeg 合并为 mp4
    9. 清理临时文件（ts、key、m3u8）
    """
    base_url = 'https://www.langfangshuzhi.com/vodplay/3258-1-1.html'
    enc_key_url = 'https://hn.bfvvs.com/play/hls/penWV7a7/enc.key'

    # 获取视频信息
    data = get_m3u8_url(base_url)
    m3u8_url = data['m3u8_url']
    title = data['title']

    # 创建存储目录
    file_path = f'movie/{title}'
    file_name = title + '.m3u8'
    full_file_path = f'{file_path}/{file_name}'

    # 下载初始 m3u8 和密钥
    parse_m3u8_url(m3u8_url, file_path, file_name)
    download_key(enc_key_url, file_path)

    # 检查是否为多级 m3u8，如果是则循环下载下一级
    confirm = confirm_m3u8(full_file_path, m3u8_url)
    while confirm:
        parse_m3u8_url(confirm, file_path, file_name)
        confirm = confirm_m3u8(full_file_path, m3u8_url)
        print('重新解析m3u8')
    print('解析完成')

    # 获取所有 ts 片段的 URL 列表
    tasks_urls = create_tasks(full_file_path, m3u8_url)

    # 并发下载所有 ts 片段
    await download_tasks(tasks_urls, file_path)

    # 重写 m3u8 文件，使路径指向本地 ts 文件
    local_m3u8 = re_write_m3u8(file_path, file_name)

    # 合并视频
    success = merge_video(file_path, local_m3u8, title)
    if success:
        # 合并成功后删除临时文件
        remove_files(file_path)

if __name__ == '__main__':
    # 启动异步主函数
    asyncio.run(main())