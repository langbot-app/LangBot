export interface IPluginMarketCardVO {
    pluginId: string;
    author: string,
    version: string,
    name: string,
    description: string,
    starCount: number,
    githubURL: string,
}

export class PluginMarketCardVO implements IPluginMarketCardVO {
    pluginId: string;
    description: string;
    name: string;
    author: string;
    version: string;
    githubURL: string;
    starCount: number;

    constructor(prop: IPluginMarketCardVO) {
        this.description = prop.description
        this.name = prop.name
        this.author = prop.author
        this.version = prop.version
        this.githubURL = prop.githubURL
        this.starCount = prop.starCount
        this.pluginId = prop.pluginId
    }


}
