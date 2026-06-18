if not get_option('plugins')
  subdir_done()
endif

qemu_plugin_symbols = configure_file(
  input: files('../include/plugins/qemu-plugin.h'),
  output: 'qemu-plugin.symbols',
  capture: true,
  command: [files('../scripts/qemu-plugin-symbols.py'), '@INPUT@'])

# Modules need more symbols than just those in plugins/qemu-plugins.symbols
if not enable_modules
  if host_os == 'darwin'
    # PANDBox macOS port: the ld64 -exported_symbols_list is an allowlist, so
    # symbols not listed are demoted to local. Upstream only lists qemu_* which
    # hides the panda API — but libpanda (the pypanda/pandare2 shared object) and
    # the plugin dylibs both resolve panda_*/ppp_*/rr_* from libpanda at load
    # time. Append those wildcards so they stay exported on macOS, matching the
    # export-all behavior libpanda gets on Linux. (Over-exporting from the qemu
    # executable is harmless.)
    panda_ld64_syms = '''sed -ne 's/^[[:space:]]*\(qemu_.*\);/_\1/p' "$0"
printf '_panda_*\n_ppp_*\n_rr_*\n_pandalog*\n_pcb_*\n'
'''
    configure_file(
      input: qemu_plugin_symbols,
      output: 'qemu-plugins-ld64.symbols',
      capture: true,
      command: ['sh', '-c', panda_ld64_syms, '@INPUT@'])
    # Apply the ld64 allowlist to the qemu executable ONLY (emulator_export_only_args),
    # NOT to libpanda — libpanda must export all of its globals so the plugin
    # dylibs and pandare2 can resolve panda_*/ppp_*/rr_*/qemu_* internals at load.
    emulator_export_only_args += ['-Wl,-exported_symbols_list,plugins/qemu-plugins-ld64.symbols']
  elif host_os == 'windows' and meson.get_compiler('c').get_id() == 'clang'
    # LLVM/lld does not support exporting specific symbols. However, it works
    # out of the box with dllexport/dllimport attribute we set in the code.
  else
    emulator_link_args += ['-Xlinker', '--dynamic-list=' + qemu_plugin_symbols.full_path()]
  endif
endif

if host_os == 'windows'
  # Generate a .lib file for plugins to link against.
  # First, create a .def file listing all the symbols a plugin should expect to have
  # available in qemu
  win32_plugin_def = configure_file(
    input: qemu_plugin_symbols,
    output: 'qemu_plugin_api.def',
    capture: true,
    command: [python, '-c', 'import fileinput, re; print("EXPORTS", end=""); [print(re.sub(r"[{};]", "", line), end="") for line in fileinput.input()]', '@INPUT@'])

  # then use dlltool to assemble a delaylib.
  # The delaylib will have an "imaginary" name (qemu.exe), that is used by the
  # linker file we add with plugins (win32_linker.c) to identify that we want
  # to find missing symbols in current program.
  win32_qemu_plugin_api_link_flags = ['-Lplugins', '-lqemu_plugin_api']
  if meson.get_compiler('c').get_id() == 'clang'
    # With LLVM/lld, delaylib is specified at link time (-delayload)
    dlltool = find_program('llvm-dlltool', required: true)
    dlltool_cmd = [dlltool, '-d', '@INPUT@', '-l', '@OUTPUT@', '-D', 'qemu.exe']
    win32_qemu_plugin_api_link_flags += ['-Wl,-delayload=qemu.exe']
  else
    # With gcc/ld, delay lib is built with a specific delay parameter.
    dlltool = find_program('dlltool', required: true)
    dlltool_cmd = [dlltool, '--input-def', '@INPUT@',
                   '--output-delaylib', '@OUTPUT@', '--dllname', 'qemu.exe']
  endif
  win32_qemu_plugin_api = configure_file(
    input: win32_plugin_def,
    output: 'libqemu_plugin_api.a',
    command: dlltool_cmd
  )
  win32_qemu_plugin_api_lib = static_library('win32_qemu_plugin_api',
                                             link_depends: win32_qemu_plugin_api)
endif

if host_os == 'windows'
  plugins_deps = declare_dependency(sources: [files('win32_linker.c')],
                                    include_directories: '../include/plugins',
                                    link_with: win32_qemu_plugin_api_lib,
                                    link_args: win32_qemu_plugin_api_link_flags,
                                    dependencies: glib)
else
  plugins_deps = declare_dependency(include_directories: '../include/plugins',
                                    dependencies: glib)
endif

user_ss.add(files('user.c', 'api-user.c'))
system_ss.add(files('system.c', 'api-system.c'))

user_ss.add(files('api.c', 'core.c'))
system_ss.add(files('api.c', 'core.c'))

common_ss.add(files('loader.c'))

