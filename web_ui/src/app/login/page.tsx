'use client';
import { Button, Input, Form, Checkbox, Divider } from 'antd';
import { GoogleOutlined, AppleOutlined, LockOutlined, UserOutlined } from '@ant-design/icons';
import styles from './login.module.css';
import { useState } from 'react';

export default function Home() {
    const [form] = Form.useForm();
    const [rememberMe, setRememberMe] = useState(false);

    return (
        // 使用 Ant Design 的组件库，使用 antd 的样式
        // 仅前端样式，无交互功能。

        <div className={styles.container}>
            {/* login 类是整个 container，使用 flex 左右布局 */}
            <div className={styles.login}>
                {/* left 为注册的表单，需要填入的内容有：邮箱，密码 */}
                <div className={styles.left}>
                    <div className={styles.loginForm}>
                        <h1 className={styles.title}>欢迎回来</h1>
                        <Form form={form} layout="vertical">
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
                                <a href="#">忘记密码?</a>
                            </div>

                            <Button type="primary" size="large" className={styles.loginButton} block>
                                登录
                            </Button>

                            <Divider className={styles.divider}>或</Divider>

                            <div className={styles.socialLogin}>
                                <Button
                                    className={styles.socialButton}
                                    icon={<GoogleOutlined />}
                                    size="large"
                                >
                                    使用谷歌账号登录
                                </Button>
                            </div>
                            <div style={{ height: '10px' }}></div>
                            <div className={styles.socialLogin}>
                                <Button
                                    className={styles.socialButton}
                                    icon={<AppleOutlined />}
                                    size="large"
                                >
                                    使用苹果账号登录
                                </Button>
                            </div>
                        </Form>
                    </div>
                </div>
                {/* right 为左侧布局，显示的是应用截图，测试阶段使用 picsum.photos 代替 */}
                <div className={styles.right}>
                    <img
                        src="https://picsum.photos/800/1000"
                        alt="应用预览"
                        style={{
                            width: '100%',
                            height: '100%',
                            objectFit: 'cover',
                            objectPosition: 'left center'
                        }}
                    />
                    {/* 在右上角添加logo */}
                    <div className={styles.logoContainer}>
                        <img
                            src="https://picsum.photos/100/100"
                            alt="Logo"
                            className={styles.logo}
                        />
                    </div>
                </div>
            </div>
        </div>
    );
}
