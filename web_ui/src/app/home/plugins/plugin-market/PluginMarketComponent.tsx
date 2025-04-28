"use client"

import { useCallback, useEffect, useState } from "react";
import styles from "@/app/home/plugins/plugins.module.css";
import { PluginMarketCardVO } from "@/app/home/plugins/plugin-market/plugin-market-card/PluginMarketCardVO";
import PluginMarketCardComponent from "@/app/home/plugins/plugin-market/plugin-market-card/PluginMarketCardComponent";
import { Input, Pagination } from "antd";
import { debounce } from "lodash"

export default function PluginMarketComponent() {
    const [marketPluginList, setMarketPluginList] = useState<PluginMarketCardVO[]>([])
    const [searchKeyword, setSearchKeyword] = useState("")
    const [currentPage, setCurrentPage] = useState(1)
    const [totalItems, setTotalItems] = useState(0)
    const [loading, setLoading] = useState(false)
    const pageSize = 10 // 每页显示的项目数量

    useEffect(() => {
        fetchPlugins(searchKeyword, currentPage)
    }, [currentPage])

    // 获取插件列表，整合了搜索和分页功能
    async function fetchPlugins(keyword: string = "", page: number = 1): Promise<void> {
        setLoading(true)
        try {
            // 实际应用中，这里应该调用API获取数据
            const result = await mockFetchPlugins(keyword, page, pageSize)
            setMarketPluginList(result.data)
            setTotalItems(result.total)
        } finally {
            setLoading(false)
        }
    }

    // 模拟从API获取数据
    async function mockFetchPlugins(keyword: string, page: number, pageSize: number): Promise<{ data: PluginMarketCardVO[], total: number }> {
        // 模拟API延迟
        await new Promise(resolve => setTimeout(resolve, 300))

        // 创建模拟数据
        const allPlugins: PluginMarketCardVO[] = []
        const totalPlugins = 50 // 模拟总数据量

        for (let i = 0; i < totalPlugins; i++) {
            allPlugins.push(new PluginMarketCardVO({
                pluginId: `plugin-${i}`,
                description: `这是插件 ${i} 的描述，包含一些详细信息`,
                name: `插件 ${i}`,
                author: `/author-${i % 5}`, // 模拟5个不同的作者
                version: `0.${i % 10}`,
                githubURL: `https://github.com/author-${i % 5}/plugin-${i}`,
                starCount: 10 + Math.floor(Math.random() * 100)
            }))
        }

        // 根据关键词过滤
        const filtered = keyword
            ? allPlugins.filter(p =>
                p.name.toLowerCase().includes(keyword.toLowerCase()) ||
                p.description.toLowerCase().includes(keyword.toLowerCase()))
            : allPlugins

        // 分页处理
        const start = (page - 1) * pageSize
        const end = start + pageSize
        const paginatedData = filtered.slice(start, end)

        return {
            data: paginatedData,
            total: filtered.length
        }
    }

    function onInputSearchKeyword(keyword: string) {
        setSearchKeyword(keyword)
        setCurrentPage(1) // 搜索时重置为第一页
        debounceSearch(keyword)
    }

    const debounceSearch = useCallback(
        debounce((keyword: string) => {
            fetchPlugins(keyword, 1)
        }, 500), []
    )

    function handlePageChange(page: number) {
        setCurrentPage(page)
    }

    return (
        <div className={`${styles.marketComponentBody}`}>
            <Input
                style={{
                    width: '300px',
                    marginBottom: '10px',
                }}
                value={searchKeyword}
                placeholder="搜索插件"
                onChange={(e) => onInputSearchKeyword(e.target.value)}
            />
            <div className={`${styles.pluginListContainer}`}>
                {loading ? (
                    <div style={{ textAlign: 'center', padding: '20px' }}>加载中...</div>
                ) : marketPluginList.length === 0 ? (
                    <div style={{ textAlign: 'center', padding: '20px' }}>没有找到匹配的插件</div>
                ) : (
                    marketPluginList.map((vo, index) => (
                        <div key={`${vo.pluginId}-${index}`}>
                            <PluginMarketCardComponent cardVO={vo} />
                        </div>
                    ))
                )}
            </div>
            {totalItems > 0 && (
                <div style={{ display: 'flex', justifyContent: 'center', width: '100%', marginTop: '20px' }}>
                    <Pagination
                        current={currentPage}
                        total={totalItems}
                        pageSize={pageSize}
                        onChange={handlePageChange}
                        showSizeChanger={false}
                    />
                </div>
            )}
        </div>
    )
}
