"use client";

import { Button, Typography, Space, Layout, Row, Col, Result } from 'antd';
import { useRouter } from 'next/navigation';
import Image from 'next/image';

const { Title, Paragraph } = Typography;

export default function NotFound() {
    const router = useRouter();

    return (
        <Layout style={{ minHeight: '100vh', background: 'white' }}>
            <Row justify="center" align="middle" style={{ minHeight: '100vh' }}>
                <Col xs={22} sm={20} md={18} lg={14} xl={10}>
                    <div className="error-container" style={{ width: '100%', padding: '20px 0', textAlign: 'center' }}>
                        <div className="error-card" style={{
                            display: 'flex',
                            flexDirection: 'column',
                            alignItems: 'center',
                            padding: '24px'
                        }}>
                            {/* Ant Design 图标，可以换成 Langbot 的 Logo */}
                            <div style={{ marginBottom: '20px', maxWidth: '100%', height: 'auto' }}>
                                <Result
                                    status="404"
                                    title={null}
                                    subTitle={null}
                                    style={{ padding: 0 }}
                                />
                            </div>

                            <div className="error-text" style={{ textAlign: 'center', marginBottom: '24px' }}>
                                <Title level={1} style={{ margin: '0 0 16px 0', fontSize: '72px', fontWeight: 'bold', color: '#333' }}>
                                    404
                                </Title>
                                <Title level={3} style={{ margin: '0 0 8px 0', fontWeight: 'normal', color: '#333' }}>
                                    页面不存在
                                </Title>
                                <Paragraph style={{ fontSize: '16px', color: '#666', maxWidth: '450px', margin: '0 auto 32px auto' }}>
                                    您要查找的页面似乎不存在。请检查您输入的 URL 是否正确，或者返回首页。
                                </Paragraph>
                            </div>

                            <div className="error-button" style={{ marginBottom: '24px' }}>
                                <Space>
                                    <Button type="primary" style={{
                                        backgroundColor: '#2288ee',
                                        borderColor: '#2288ee',
                                        borderRadius: '4px',
                                        height: '36px',
                                        padding: '0 16px'
                                    }} onClick={() => router.back()}>
                                        上一级
                                    </Button>
                                    <Button style={{
                                        borderColor: '#d9d9d9',
                                        borderRadius: '4px',
                                        height: '36px',
                                        padding: '0 16px'
                                    }} onClick={() => router.push('/')}>
                                        返回主页
                                    </Button>
                                </Space>
                            </div>

                            <div className="error-support" style={{ textAlign: 'center', marginTop: '16px' }}>
                                <Paragraph style={{ fontSize: '14px', color: '#666' }}>
                                    需要帮助吗？您可以联系 <a href="mailto:support@qq.com" style={{ color: '#000', textDecoration: 'none' }}>support@qq.com</a>
                                </Paragraph>
                            </div>
                        </div>
                    </div>
                </Col>
            </Row>
        </Layout>
    );
}
