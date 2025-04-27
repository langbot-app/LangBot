'use client';
import { Button, Input, Form, Checkbox, Divider } from 'antd';
import {GoogleOutlined, AppleOutlined, LockOutlined, UserOutlined, QqCircleFilled, QqOutlined} from '@ant-design/icons';
import styles from './login.module.css';
import {useEffect, useState} from 'react';


import {httpClient} from "@/app/infra/http/HttpClient";
import '@ant-design/v5-patch-for-react-19';
import {useRouter} from "next/navigation";


export default function Home() {
    const router = useRouter();
    const [form] = Form.useForm<LoginField>();
    const [rememberMe, setRememberMe] = useState(false);
    const [isRegisterMode, setIsRegisterMode] = useState(false);
    const [isInitialized, setIsInitialized] = useState(false)

    useEffect(() => {
        getIsInitialized()
    }, [])


    // 检查是否为首次启动项目，只为首次启动的用户提供注册资格
    function getIsInitialized() {
        httpClient.checkIfInited().then(res => {
            setIsInitialized(res.initialized)
        }).catch(err => {
            console.log("error at getIsInitialized: ", err)
        })
    }

    function handleFormSubmit(formField: LoginField) {
        if (isRegisterMode) {
            handleRegister(formField.email, formField.password);
        } else {
            handleLogin(formField.email, formField.password)
        }
    }

    function handleRegister(username: string, password: string) {
        httpClient.initUser(username, password).then(res => {
            console.log("init user success: ", res)
        }).catch(err => {
            console.log("init user error: ", err)
        })
    }

    function handleLogin(username: string, password: string) {
        httpClient.authUser(username, password).then(res => {
            localStorage.setItem("token", res.token)
            console.log("login success: ", res)
            router.push("/home")
        }).catch(err => {
            console.log("login error: ", err)
        })
    }


    return (
        // 使用 Ant Design 的组件库，使用 antd 的样式
        // 仅前端样式，无交互功能。

        <div className={styles.container}>
            {/* login 类是整个 container，使用 flex 左右布局 */}
            <div className={styles.login}>
                {/* left 为注册的表单，需要填入的内容有：邮箱，密码 */}
                <div className={styles.left}>
                    <div className={styles.loginForm}>
                        {
                            isRegisterMode &&
                            <h1 className={styles.title}>注册 LangBot 账号</h1>
                        }
                        {
                            !isRegisterMode &&
                            <h1 className={styles.title}>欢迎回到 LangBot</h1>
                        }
                        <Form
                            form={form}
                            layout="vertical"
                            onFinish={(values) => {
                                handleFormSubmit(values)
                            }}
                        >
                            <Form.Item
                                name="email"
                                rules={[
                                    { required: true, message: '请输入邮箱!' },
                                    { type: 'email', message: '请输入有效的邮箱地址!' }
                                ]}
                            >
                                <Input
                                    placeholder="输入邮箱地址"
                                    size="large"
                                    prefix={<UserOutlined />}
                                />
                            </Form.Item>

                            <Form.Item
                                name="password"
                                rules={[
                                    { required: true, message: '请输入密码!' }
                                ]}
                            >
                                <Input.Password
                                    placeholder="输入密码"
                                    size="large"
                                    prefix={<LockOutlined />}
                                />
                            </Form.Item>

                            <div className={styles.rememberMe}>
                                <Checkbox
                                    checked={rememberMe}
                                    onChange={(e) => setRememberMe(e.target.checked)}
                                >
                                    30天内自动登录
                                </Checkbox>
                                <span>
                                    <a href="#" className={`${styles.forgetPassword}`}>忘记密码?</a>
                                    {
                                        !isRegisterMode &&
                                        <a href=""
                                           onClick={(event) => {
                                               setIsRegisterMode(true)
                                               event.preventDefault()
                                           }}
                                        >去注册？</a>
                                    }
                                    {
                                        isRegisterMode &&
                                        <a href=""
                                           onClick={(event) => {
                                               setIsRegisterMode(false)
                                               event.preventDefault()
                                           }}
                                        >去登录</a>
                                    }
                                </span>
                            </div>


                            <Button
                                type="primary"
                                size="large"
                                className={styles.loginButton}
                                block
                                htmlType="submit"
                                disabled={isRegisterMode && isInitialized}
                            >
                                {
                                    isRegisterMode ? (
                                        isInitialized ? "暂不提供注册" : "注册"
                                    ) : "登录"
                                }
                            </Button>


                            <Divider className={styles.divider}>或</Divider>

                            <div className={styles.socialLogin}>
                                <Button
                                    className={styles.socialButton}
                                    icon={<GoogleOutlined />}
                                    size="large"
                                    disabled={true}
                                >
                                    使用谷歌账号登录
                                </Button>
                            </div>
                            <div style={{ height: '10px' }}></div>
                            <div className={styles.socialLogin}>
                                <Button
                                    className={styles.socialButton}
                                    icon={<QqOutlined />}
                                    size="large"
                                    disabled={true}
                                >
                                    使用QQ账号登录
                                </Button>
                            </div>
                        </Form>
                    </div>
                </div>
            </div>
        </div>
    );
}

interface LoginField {
    email: string;
    password: string;
}