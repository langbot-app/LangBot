"use client"

import '@ant-design/v5-patch-for-react-19';
import styles from "./layout.module.css"
import HomeSidebar from "@/app/home/components/home-sidebar/HomeSidebar";
import HomeTitleBar from "@/app/home/components/home-titlebar/HomeTitleBar";
import React, { useState } from "react";
import { SidebarChildVO } from "@/app/home/components/home-sidebar/HomeSidebarChild";
import { useRouter } from 'next/navigation';
import { Layout } from 'antd';

const { Sider, Content } = Layout;

export default function HomeLayout({
    children
}: Readonly<{
    children: React.ReactNode;
}>) {
    const router = useRouter();
    const [title, setTitle] = useState<string>("")
    const onSelectedChange = (child: SidebarChildVO) => {
        setTitle(child.name)
    }

    return (
        <Layout className={styles.homeLayoutContainer}>
            {/* homeLayoutContainer 是整个容器的入口,使用 flex 的左右布局 */}

            <Sider className="left">
                <HomeSidebar
                    onSelectedChange={onSelectedChange}
                />
                {/* HomeSidebar 为侧边栏 */}
            </Sider>

            <Layout className="right">
                {/* right 为内容显示区域，right使用 flex 上下布局，right 使用 flex 布局吃掉剩余部分 */}

                <HomeTitleBar title={title} />

                <Content className={styles.main}>
                    {/* mainContent 为主页面 */}
                    {children}
                </Content>
            </Layout>
        </Layout>
    )
}
