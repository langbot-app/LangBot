import {SidebarChildVO} from "@/app/home/components/home-sidebar/HomeSidebarChild";

export const sidebarConfigList = [
    new SidebarChildVO({
        id: "llm-config",
        name: "大模型配置",
        icon: "",
        route: "/home/llm-config",
    }),
    new SidebarChildVO({
        id: "platform-config",
        name: "机器人配置",
        icon: "",
        route: "/home/bot-config",
    }),
    new SidebarChildVO({
        id: "plugin-config",
        name: "插件配置",
        icon: "",
        route: "/home/plugin-config",
    }),
    new SidebarChildVO({
        id: "pipeline-config",
        name: "流水线配置",
        icon: "",
        route: "/home/pipeline-config",
    })
]
