"""Apply Square Enix's changes to cocos2d-x 3.2 (docs/ENGINE_CHANGES.md) to the sources in third_party/.

python tools/apply_engine_changes.py

Every change is marked "KHUx-Native". Layout and vtable order follow the game exactly (checked by
tools/engine_diff.py); bodies not read from the binary yet are marked TODO. Run once on fresh sources (build_cocos.sh
does it); patches/cocos2d-x-3.2.patch is then regenerated from the result.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
C = ROOT / 'third_party' / 'cocos2d-x-cocos2d-x-3.2'
SE = 'KHUx-Native (Square Enix)'


def edit(rel, *pairs, count=1):
    p = C / rel
    s = p.read_text(encoding='utf-8', errors='surrogateescape')
    nl = '\r\n' if '\r\n' in s else '\n'
    for old, new in pairs:
        old_n, new_n = old.replace('\n', nl), new.replace('\n', nl)
        if new_n in s:
            continue                                         # already applied (new contains old: test it first)
        n = s.count(old_n)
        if n != count:
            sys.exit(f'{rel}: expected {count} match(es) of {old[:70]!r}, found {n}')
        s = s.replace(old_n, new_n)
    p.write_text(s, encoding='utf-8', errors='surrogateescape')


# ---------------------------------------------------------------- Color4F::CLEAR (the game has it; 3.2 does not)
edit('cocos/base/ccTypes.h',
     ('    static const Color4F WHITE;\n',
      '    static const Color4F WHITE;\n'
      f'    static const Color4F CLEAR;   // {SE}: transparent black (0, 0, 0, 0)\n'))
edit('cocos/base/ccTypes.cpp',
     ('const Color4F Color4F::WHITE  (    1,     1,     1, 1);\n',
      'const Color4F Color4F::WHITE  (    1,     1,     1, 1);\n'
      f'const Color4F Color4F::CLEAR  (    0,     0,     0, 0);   // {SE}\n'))

# ---------------------------------------------------------------- Node: color effect (2 virtuals, 2 Color4F)
edit('cocos/2d/CCNode.h',
     ('    virtual bool isOpacityModifyRGB() const { return false; };\n',
      '    virtual bool isOpacityModifyRGB() const { return false; };\n'
      f'    /** {SE}: color effect - a multiply color (r, g, b, a) and an add color, each value in [-1, 1].\n'
      '     * A plain non-negative multiply becomes setColor / setOpacity; anything else needs updateGLProgram. */\n'
      '    virtual void setColorEffect(float mulR, float mulG, float mulB, float mulA,\n'
      '                                float addR, float addG, float addB, float addA);\n'),
     ('    virtual void updateColor() {}\n',
      '    virtual void updateColor() {}\n'
      f'    /** {SE}: picks the shader for the color effect (Sprite overrides it). */\n'
      '    virtual void updateGLProgram() {}\n'),
     ('    bool        _cascadeOpacityEnabled;\n',
      '    bool        _cascadeOpacityEnabled;\n'
      f'    // {SE}: the color effect (0x1F0 / 0x200 in the game)\n'
      '    Color4F     _colorMultiply = Color4F::WHITE;\n'
      '    Color4F     _colorAdd = Color4F::CLEAR;\n'))
edit('cocos/2d/CCNode.cpp',
     ('void Node::updateDisplayedOpacity(GLubyte parentOpacity)',
      f'// {SE}: Node::setColorEffect (0x896480 in the game)\n'
      'void Node::setColorEffect(float mulR, float mulG, float mulB, float mulA, float addR, float addG, float addB, float addA)\n'
      '{\n'
      '    auto clamp = [](float v) { return v >= 1.0f ? 1.0f : (v <= -1.0f ? -1.0f : v); };\n'
      '    _colorMultiply = Color4F(clamp(mulR), clamp(mulG), clamp(mulB), clamp(mulA));\n'
      '    _colorAdd = Color4F(clamp(addR), clamp(addG), clamp(addB), clamp(addA));\n'
      '    if (_colorMultiply != Color4F::WHITE && _colorAdd == Color4F::CLEAR && mulB >= 0.0f && mulG >= 0.0f && mulR >= 0.0f)\n'
      '    {\n'
      '        // a plain multiply: ordinary color and opacity (the unclamped arguments, as the game does)\n'
      '        _colorMultiply = Color4F::WHITE;\n'
      '        setColor(Color3B((GLubyte)(unsigned int)(mulR * 255.0f), (GLubyte)(unsigned int)(mulG * 255.0f),\n'
      '                         (GLubyte)(unsigned int)(mulB * 255.0f)));\n'
      '        setOpacity(mulA > 0.0f ? (GLubyte)(unsigned int)(mulA * 255.0f) : 0);\n'
      '    }\n'
      '    else\n'
      '    {\n'
      '        setColor(Color3B::WHITE);\n'
      '        setOpacity(255);\n'
      '    }\n'
      '    updateGLProgram();\n'
      '}\n'
      '\n'
      'void Node::updateDisplayedOpacity(GLubyte parentOpacity)'))

# ---------------------------------------------------------------- QuadCommand: the colors reach the renderer
edit('cocos/renderer/CCQuadCommand.h',
     ('    void init(float globalOrder, GLuint texutreID, GLProgramState* shader, BlendFunc blendType, V3F_C4B_T2F_Quad* quads, ssize_t quadCount,\n'
      '              const Mat4& mv);\n',
      '    void init(float globalOrder, GLuint texutreID, GLProgramState* shader, BlendFunc blendType, V3F_C4B_T2F_Quad* quads, ssize_t quadCount,\n'
      f'              const Mat4& mv, const Color4F& colorMultiply = Color4F::WHITE, const Color4F& colorAdd = Color4F::CLEAR);   // {SE}: + the colors\n'),
     ('    Mat4 _mv;\n};',
      '    Mat4 _mv;\n'
      f'    // {SE}: the node\'s color effect (0x68 / 0x78 in the game)\n'
      '    Color4F _colorMultiply = Color4F::WHITE;\n'
      '    Color4F _colorAdd = Color4F::CLEAR;\n'
      '};'))
edit('cocos/renderer/CCQuadCommand.cpp',
     ('void QuadCommand::init(float globalOrder, GLuint textureID, GLProgramState* glProgramState, BlendFunc blendType, V3F_C4B_T2F_Quad* quad, ssize_t quadCount, const Mat4 &mv)',
      'void QuadCommand::init(float globalOrder, GLuint textureID, GLProgramState* glProgramState, BlendFunc blendType, V3F_C4B_T2F_Quad* quad, ssize_t quadCount, const Mat4 &mv,\n'
      '                       const Color4F& colorMultiply, const Color4F& colorAdd)'),
     ('    if( _textureID != textureID || _blendType.src != blendType.src || _blendType.dst != blendType.dst || _glProgramState != glProgramState) {\n'
      '\n'
      '        _textureID = textureID;\n'
      '        _blendType = blendType;\n'
      '        _glProgramState = glProgramState;\n',
      f'    // {SE}: a different color effect is a different material too\n'
      '    if( _textureID != textureID || _blendType.src != blendType.src || _blendType.dst != blendType.dst || _glProgramState != glProgramState\n'
      '        || _colorMultiply != colorMultiply || _colorAdd != colorAdd) {\n'
      '\n'
      '        _textureID = textureID;\n'
      '        _blendType = blendType;\n'
      '        _glProgramState = glProgramState;\n'
      '        _colorMultiply = colorMultiply;\n'
      '        _colorAdd = colorAdd;\n'))

# ---------------------------------------------------------------- TTFConfig + Label
edit('cocos/2d/CCLabel.h',
     ('    int outlineSize;\n',
      '    int outlineSize;\n'
      f'    // {SE}: two more flags (passed on to FontFreeType::create); meaning TODO\n'
      '    bool flag1 = false;\n'
      '    bool flag2 = false;\n'),
     ('    bool _insideBounds;                     /// whether or not the sprite was inside bounds the previous frame\n',
      '    bool _insideBounds;                     /// whether or not the sprite was inside bounds the previous frame\n'
      '\n'
      f'    // {SE}: indent and line spacing (0x4C8 / 0x4CC in the game)\n'
      '    float _indent = 0.0f;\n'
      '    float _lineSpacing = 0.0f;\n'
      'public:\n'
      '    void setIndent(float indent) { if (_indent != indent) { _indent = indent; _contentDirty = true; } }\n'
      '    void setLineSpacing(float spacing) { if (_lineSpacing != spacing) { _lineSpacing = spacing; _contentDirty = true; } }\n'))

# ---------------------------------------------------------------- text input: a new line, keyboard callbacks
edit('cocos/base/CCIMEDelegate.h',
     ('    virtual void insertText(const char * text, size_t len) {CC_UNUSED_PARAM(text);CC_UNUSED_PARAM(len);}\n',
      '    virtual void insertText(const char * text, size_t len) {CC_UNUSED_PARAM(text);CC_UNUSED_PARAM(len);}\n'
      f'    /** {SE}: a new line typed in a multi-line field. */\n'
      '    virtual void insertTextNewLine(const char * text, size_t len) {CC_UNUSED_PARAM(text);CC_UNUSED_PARAM(len);}\n'))
edit('cocos/2d/CCTextFieldTTF.h',
     ('    virtual bool isSecureTextEntry();\n',
      '    virtual bool isSecureTextEntry();\n'
      f'    // {SE}: keyboard callbacks (bodies TODO from the binary)\n'
      '    virtual void keyboardWillShow(IMEKeyboardNotificationInfo& info) override { CC_UNUSED_PARAM(info); }\n'
      '    virtual void keyboardDidShow(IMEKeyboardNotificationInfo& info) override { CC_UNUSED_PARAM(info); }\n'
      '    virtual void keyboardWillHide(IMEKeyboardNotificationInfo& info) override { CC_UNUSED_PARAM(info); }\n'
      '    virtual void keyboardDidHide(IMEKeyboardNotificationInfo& info) override { CC_UNUSED_PARAM(info); }\n'),
     ('    virtual void insertText(const char * text, size_t len) override;\n',
      '    virtual void insertText(const char * text, size_t len) override;\n'
      f'    virtual void insertTextNewLine(const char * text, size_t len) override {{ insertText(text, len); }}   // {SE}: body TODO\n'),
     ('    class LengthStack;\n    LengthStack * _lens;\n',
      '    class LengthStack;\n    LengthStack * _lens;\n'
      f'    // {SE}: 8 bytes (0x504 / 0x508 in the game); meaning TODO\n'
      '    int _khux504 = 0;\n'
      '    int _khux508 = 0;\n'))
edit('cocos/ui/UITextField.h',
     ('    bool _deleteBackward;\n',
      '    bool _deleteBackward;\n'
      f'    // {SE}: multi-line input (0x52C / 0x530 in the game)\n'
      '    bool _newLineEnabled = false;\n'
      '    int _newLineArg = 0;\n'
      'public:\n'
      '    void setNewLine(bool enabled, int arg) { _newLineEnabled = enabled; _newLineArg = arg; }   // body TODO\n'))
edit('extensions/GUI/CCEditBox/CCEditBox.h',
     ('    Color3B _colText;\n    Color3B _colPlaceHolder;\n',
      '    Color3B _colText;\n'
      f'    Color3B _colEditing = Color3B::WHITE;   // {SE}: the text color while editing\n'
      '    Color3B _colPlaceHolder;\n'),
     ('    int   _scriptEditBoxHandler;\n',
      '    int   _scriptEditBoxHandler;\n'
      f'    int   _khux398 = 0;   // {SE}: 4 bytes (0x398 in the game); meaning TODO\n'
      'public:\n'
      '    void setEditingFontColor(const Color3B& color) { _colEditing = color; }   // body TODO\n'))

# ---------------------------------------------------------------- FileUtils
edit('cocos/platform/CCFileUtils.h',
     ('    virtual std::string fullPathForFilename(const std::string &filename);\n',
      '    virtual std::string fullPathForFilename(const std::string &filename);\n'
      f'    virtual std::string fullPathForFilenameEx(const std::string &filename) {{ return fullPathForFilename(filename); }}   // {SE}: body TODO\n'),
     ('    virtual std::string getWritablePath() const = 0;\n',
      '    virtual std::string getWritablePath() const = 0;\n'
      f'    // {SE}: (return types of the first three TODO from the binary)\n'
      '    virtual std::string getCachePath() const = 0;\n'
      '    virtual std::string getExecutablePath() const = 0;\n'
      '    virtual std::string getLoadedFiles() const = 0;\n'
      '    virtual bool createDirectory(const std::string& path, bool recursive) = 0;\n'))
edit('cocos/platform/win32/CCFileUtilsWin32.h',
     ('    virtual std::string getWritablePath() const;\n',
      '    virtual std::string getWritablePath() const;\n'
      f'    // {SE}: the Android build\'s additions (stubs on Windows)\n'
      '    virtual std::string getCachePath() const override { return getWritablePath(); }\n'
      '    virtual std::string getExecutablePath() const override { return std::string(); }\n'
      '    virtual std::string getLoadedFiles() const override { return std::string(); }\n'
      '    virtual bool createDirectory(const std::string& path, bool recursive) override { return false; }\n'))

# ---------------------------------------------------------------- the Android build's members (unused here)
AND = f'   // {SE}: the Android build has this member (layout)'
edit('cocos/renderer/CCTextureAtlas.h',
     ('#if CC_ENABLE_CACHE_TEXTURE_DATA\n    EventListenerCustom* _rendererRecreatedListener;',
      '#if CC_ENABLE_CACHE_TEXTURE_DATA || KHUX_ANDROID_LAYOUT' + AND + '\n    EventListenerCustom* _rendererRecreatedListener;'))
edit('cocos/renderer/CCRenderer.h',
     ('#if CC_ENABLE_CACHE_TEXTURE_DATA\n    EventListenerCustom* _cacheTextureListener;',
      '#if CC_ENABLE_CACHE_TEXTURE_DATA || KHUX_ANDROID_LAYOUT' + AND + '\n    EventListenerCustom* _cacheTextureListener;'))
ANDROID_OR_WP8 = 'CC_TARGET_PLATFORM == CC_PLATFORM_ANDROID || CC_TARGET_PLATFORM == CC_PLATFORM_WP8'
for rel, cond, member in (('cocos/renderer/CCMeshCommand.h', ANDROID_OR_WP8, '_rendererRecreatedListener'),
                          ('cocos/3d/CCMesh.h', ANDROID_OR_WP8, '_rendererRecreatedListener'),
                          ('cocos/renderer/CCGLProgramState.h', 'CC_TARGET_PLATFORM == CC_PLATFORM_ANDROID', '_backToForegroundlistener')):
    edit(rel, (f'#if ({cond})\n    EventListenerCustom* {member};',
               f'#if ({cond}) || KHUX_ANDROID_LAYOUT{AND}\n    EventListenerCustom* {member};'))
print('applied')
