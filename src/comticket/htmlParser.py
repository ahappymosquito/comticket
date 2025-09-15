# 引入所需库
from lxml import etree
from loguru import logger
from typing import List, Optional


# --- 第 1 步: 封装代表单个页面元素的类 ---
# 这个类的实例代表一个由 lxml 找到的 HTML 元素（如一个<a>标签或一个<div>）

class Element:
    """
    封装单个 lxml 元素对象，提供简洁的接口来获取其数据。
    An object of this class represents a single lxml element.
    """

    def __init__(self, lxml_element: etree._Element):
        """
        使用一个 lxml 元素对象进行初始化。

        Args:
            lxml_element (etree._Element): lxml.etree 解析后得到的原始元素。
        """
        # 使用下划线前缀表示这是一个内部使用的变量
        self._element = lxml_element

    def get_text(self) -> str:
        """
        获取此元素内部的所有文本内容，包括所有子元素的文本。
        会自动去除首尾的空白字符。

        Returns:
            str: 元素的文本内容。
        """
        # 使用 .itertext() 可以获取所有子孙节点的文本，然后用 ''.join() 拼接
        # 这是获取一个元素完整文本内容最稳妥的方法
        return ''.join(self._element.itertext()).strip()

    def get_attribute(self, name: str) -> Optional[str]:
        """
        获取指定属性的值。

        Args:
            name (str): 属性的名称 (例如 'href', 'class', 'id')。

        Returns:
            Optional[str]: 属性的值。如果属性不存在，则返回 None。
        """
        # .get() 方法是 lxml 中获取属性的标准方式，如果属性不存在则返回 None
        return self._element.get(name)

    def get_elements(self, xpath_query: str) :
        """
        【新增】从当前元素开始，根据相对 XPath 继续查询子元素。

        Args:
            xpath_query (str): 用于查询的 XPath 表达式。
                               强烈建议使用相对路径 (以 '.' 开头)。

        Returns:
            List[Element]: 一个包含所有匹配结果的 Element 对象列表。
        """
        try:
            # 关键：xpath() 是在 self._element 这个当前元素上调用的，
            # 而不是在整个文档的 root 上调用。
            raw_elements = self._element.xpath(xpath_query)
            # logger.info(
                # f"在 <{self._element.tag}> 元素内执行相对查询: '{xpath_query}'，找到 {len(raw_elements)} 个结果。")

            # 同样，将返回的原始 lxml 元素包装成我们自定义的 Element 对象
            return [Element(el) for el in raw_elements if isinstance(el, etree._Element)]

        except etree.XPathError as e:
            logger.error(f"相对 XPath 表达式错误: '{xpath_query}'. 详细信息: {e}")
            return []


    def __repr__(self) -> str:
        """
        提供一个清晰的、可供调试的对象表示形式。
        例如，打印这个对象时会显示 <Element a> 或 <Element div>。
        """
        return f"<Element {self._element.tag}>"


# --- 第 2 步: 封装 HTML 解析器类 ---
# 这个类负责接收整个 HTML 文本，并根据 XPath 规则查询元素

class HtmlParser:
    """
    HTML 解析器，用于加载 HTML 文本并使用 XPath 提取元素。
    This class is responsible for parsing HTML text and querying elements.
    """

    def __init__(self, html_text: str):
        """
        使用 HTML 文本字符串初始化解析器。

        Args:
            html_text (str): 要解析的 HTML 页面源代码。
        """
        self.root = None
        if not html_text or not isinstance(html_text, str):
            logger.error("输入无效：html_text 必须是一个非空字符串。")
            return

        try:
            # etree.HTML() 可以解析不规范的 HTML，容错性强
            self.root = etree.HTML(html_text)
            logger.success("HTML 文本成功解析为 lxml 对象。")
        except Exception as e:
            logger.error(f"解析 HTML 时发生错误: {e}")

    def get_elements(self, xpath_query: str) -> List[Element]:
        """
        根据提供的 XPath 查询字符串，获取页面上所有匹配的元素列表。

        Args:
            xpath_query (str): 用于查询元素的 XPath 表达式。

        Returns:
            List[Element]: 一个包含所有匹配结果的 Element 对象列表。
                           如果解析失败或没有找到任何元素，则返回空列表。
        """
        if self.root is None:
            logger.warning("解析器未成功初始化，无法执行 XPath 查询。")
            return []

        try:
            # 使用 root 对象执行 xpath 查询，返回原始 lxml 元素列表
            raw_elements = self.root.xpath(xpath_query)
            logger.info(f"执行 XPath 查询: '{xpath_query}'，找到 {len(raw_elements)} 个元素。")

            # [核心] 列表推导式：将每个原始 lxml 元素包装成我们自定义的 Element 对象
            return [Element(el) for el in raw_elements if isinstance(el, etree._Element)]

        except etree.XPathError as e:
            logger.error(f"XPath 表达式错误: '{xpath_query}'. 详细信息: {e}")
            return []


if __name__ == "__main__":

    # 模拟一个 HTML 文本
    sample_html = """
    <!DOCTYPE html>
    <html>
    <body>
        <div class="content">
            <h1>文章标题 1</h1>
            <ul>
                <li><a href="/item/1" class="link">项目 1</a></li>
                <li><a href="/item/2" class="link active">项目 2</a></li>
            </ul>
        </div>
        <div class="sidebar">
            <h1>相关链接</h1>
            <ul>
                <li><a href="/related/1">相关 1</a></li>
                <li><a href="/related/2">相关 2</a></li>
            </ul>
        </div>
    </body>
    </html>
    """

    # 1. 初始化解析器
    parser = HtmlParser(sample_html)

    print("=" * 20 + " 开始链式查询 " + "=" * 20)

    # 2. 第一步：先定位到 class="content" 的 div 容器
    # 这个查询会返回一个只包含一个元素的列表
    content_divs = parser.get_elements("//div[@class='content']")

    if content_divs:
        # 获取列表中的第一个元素，即那个 div 容器
        content_div = content_divs[0]
        print(f"成功定位到容器元素: {content_div}")

        # 3. 第二步（核心）：从这个 div 容器内部，继续查找所有的 <a> 标签
        # 注意 XPath 表达式以 '.' 开头，代表“从当前节点开始”
        # 这是一个相对路径查询
        links_in_content = content_div.get_elements('.//a')

        print(f"\n从 '{content_div}' 内部查找链接:")
        if links_in_content:
            for link in links_in_content:
                print(f"  - 文本: {link.get_text()}, Href: {link.get_attribute('href')}")

        # 对比：如果直接从全局查找，会找到 sidebar 里的链接
        print("\n对比全局查询结果:")
        all_links = parser.get_elements("//a")
        for link in all_links:
            print(f"  - 文本: {link.get_text()}, Href: {link.get_attribute('href')}")