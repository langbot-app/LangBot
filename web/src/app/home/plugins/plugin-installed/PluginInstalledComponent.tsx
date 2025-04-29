"use client";

import { useState, useEffect } from "react";
import CreateCardComponent from "@/app/infra/basic-component/create-card-component/CreateCardComponent";
import { PluginCardVO } from "@/app/home/plugins/plugin-installed/PluginCardVO";
import PluginCardComponent from "@/app/home/plugins/plugin-installed/plugin-card/PluginCardComponent";
import styles from "@/app/home/plugins/plugins.module.css";
import { Modal, Input } from "antd";
import { GithubOutlined } from "@ant-design/icons";
import { httpClient } from "@/app/infra/http/HttpClient";

export default function PluginInstalledComponent() {
  const [pluginList, setPluginList] = useState<PluginCardVO[]>([]);
  const [modalOpen, setModalOpen] = useState(false);
  const [githubURL, setGithubURL] = useState("");

  useEffect(() => {
    initData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function initData() {
    getPluginList();
  }

  function getPluginList() {
    httpClient.getPlugins().then((value) => {
      setPluginList(
        value.plugins.map((plugin) => {
          return new PluginCardVO({
            author: plugin.author,
            description: plugin.description.zh_CN,
            handlerCount: 0,
            name: plugin.name,
            version: plugin.version,
            isInitialized: plugin.status === "initialized"
          });
        })
      );
    });
  }

  function handleModalConfirm() {
    installPlugin(githubURL);
    setModalOpen(false);
  }

  function installPlugin(url: string) {
    httpClient
      .installPluginFromGithub(url)
      .then(() => {
        // 安装后重新拉取
        getPluginList();
      })
      .catch((err) => {
        console.log("error when install plugin:", err);
      });
  }
  return (
    <div className={`${styles.pluginListContainer}`}>
      <Modal
        title={
          <div className={`${styles.modalTitle}`}>
            <GithubOutlined
              style={{
                fontSize: "30px",
                marginRight: "20px"
              }}
            />
          </div>
        }
        open={modalOpen}
        onOk={handleModalConfirm}
        onCancel={() => setModalOpen(false)}
        destroyOnClose={true}
      >
        <div className={`${styles.modalBody}`}>
          <div>目前仅支持从 GitHub 安装</div>
          <Input
            placeholder="请输入插件的Github链接"
            value={githubURL}
            onChange={(e) => setGithubURL(e.target.value)}
          />
        </div>
      </Modal>
      {pluginList.map((vo, index) => {
        return (
          <div key={index}
            style={{ width: "100%", height: "100%" }}>
            <PluginCardComponent cardVO={vo} />
          </div>
        );
      })}
      <CreateCardComponent
        plusSize={90}
        onClick={() => {
          setModalOpen(true);
        }}
      />
    </div>
  );
}
