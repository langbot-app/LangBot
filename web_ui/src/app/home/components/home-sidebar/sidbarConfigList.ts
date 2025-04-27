import {SidebarChildVO} from "@/app/home/components/home-sidebar/HomeSidebarChild";

export const sidebarConfigList = [
    new SidebarChildVO({
        id: "models",
        name: "模型配置",
        icon: "",
        route: "/home/models",
    }),
    new SidebarChildVO({
        id: "bots",
        name: "机器人",
        icon: "",
        route: "/home/bots",
    }),
    new SidebarChildVO({
        id: "pipelines",
        name: "流水线",
        icon: "",
        route: "/home/pipelines",
    }),
    new SidebarChildVO({
        id: "plugins",
        name: "插件管理",
        icon: "",
        route: "/home/plugins",
    }),
]
