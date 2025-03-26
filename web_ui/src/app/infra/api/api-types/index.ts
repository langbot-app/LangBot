export interface ApiResponse<T> {
    code: number;
    data: T;
    msg: string;
}

export interface I18nText {
    en_US: string;
    zh_CN: string;
}

