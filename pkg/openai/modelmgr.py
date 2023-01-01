# 提供与模型交互的抽象接口

COMPLETION_MODELS = {
    'text-davinci-003'
}

EDIT_MODELS = {

}

IMAGE_MODELS = {

}


# ModelManager
# 由session包含
class ModelMgr(object):

    using_completion_model = ""
    using_edit_model = ""
    using_image_model = ""

    def __init__(self):
        pass

    def get_using_completion_model(self):
        return self.using_completion_model

    def get_using_edit_model(self):
        return self.using_edit_model

    def get_using_image_model(self):
        return self.using_image_model
