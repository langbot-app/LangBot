"use client"

import styles from "./HomeSidebar.module.css"
import { useEffect, useState } from "react";
import { SidebarChild, SidebarChildVO } from "@/app/home/components/home-sidebar/HomeSidebarChild";
import { useRouter, usePathname, useSearchParams } from "next/navigation";
import { sidebarConfigList } from "@/app/home/components/home-sidebar/sidbarConfigList";

// TODO 侧边导航栏要加动画
export default function HomeSidebar({
    onSelectedChange
}: {
    onSelectedChange: (sidebarChild: SidebarChildVO) => void
}) {
    // 路由相关
    const router = useRouter()
    const pathname = usePathname();
    const searchParams = useSearchParams();
    // 路由被动变化时处理
    useEffect(() => {
        handleRouteChange(pathname)
    }, [pathname, searchParams]);

    const [selectedChild, setSelectedChild] = useState<SidebarChildVO>(sidebarConfigList[0])

    useEffect(() => {
        console.log('HomeSidebar挂载完成');
        initSelect()
        return () => console.log('HomeSidebar卸载');
    }, []);



    function handleChildClick(child: SidebarChildVO) {
        setSelectedChild(child)
        handleRoute(child)
        onSelectedChange(child)
    }

    function initSelect() {
        // 根据当前URL路径选择相应的菜单项，而不是总是使用第一个菜单项
        const currentPath = pathname;
        const matchedChild = sidebarConfigList.find(child => child.route === currentPath);

        if (matchedChild) {
            // 如果找到匹配的菜单项，则选择它
            setSelectedChild(matchedChild);
            onSelectedChange(matchedChild);
        } else {
            // 如果没有匹配项，则回退到默认选择第一个菜单项
            handleChildClick(sidebarConfigList[0]);
        }
    }

    function handleRoute(child: SidebarChildVO) {
        console.log(child)
        router.push(`${child.route}`)
    }

    function handleRouteChange(pathname: string) {
        // TODO 这段逻辑并不好，未来router封装好后改掉
        // 判断在home下，并且路由更改的是自己的路由子组件则更新UI
        const routeList = pathname.split('/')
        if (
            routeList[1] === "home" &&
            sidebarConfigList.find(childConfig =>
                childConfig.route === pathname
            )
        ) {
            console.log("find success")
            const routeSelectChild = sidebarConfigList.find(childConfig =>
                childConfig.route === pathname
            )
            if (routeSelectChild) {
                setSelectedChild(routeSelectChild)
            }
        }
    }


    return (
        <div className={`${styles.sidebarContainer}`}>
            {/* LangBot、ICON区域 */}
            <div className={`${styles.langbotIconContainer}`}>
                {/* icon */}
                <div className={`${styles.langbotIcon}`}>
                    L
                </div>
                <div className={`${styles.langbotText}`}>
                    Langbot
                </div>
            </div>
            {/* 菜单列表，后期可升级成配置驱动 */}
            <div>
                {
                    sidebarConfigList.map(config => {
                        return (
                            <div
                                key={config.id}
                                onClick={() => {
                                    console.log('click:', config.id)
                                    handleChildClick(config)
                                }}
                            >
                                <SidebarChild
                                    isSelected={selectedChild.id === config.id}
                                    icon={config.icon}
                                    name={config.name}
                                />
                            </div>
                        )
                    })
                }

            </div>
        </div>
    );
}