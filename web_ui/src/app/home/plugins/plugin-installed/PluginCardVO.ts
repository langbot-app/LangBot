export interface IPluginCardVO {
    author: string,
    version: string,
    name: string,
    description: string,
    handlerCount: number,
}

export class PluginCardVO implements IPluginCardVO {
    description: string;
    handlerCount: number;
    name: string;
    author: string;
    version: string;

    constructor(prop: IPluginCardVO) {
        this.description = prop.description
        this.handlerCount = prop.handlerCount
        this.name = prop.name
        this.author = prop.author
        this.version = prop.version
    }

}
