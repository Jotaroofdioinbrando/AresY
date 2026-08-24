declare i32 @printf(i8*, ...)
declare i32 @scanf(i8*, ...)
declare i32 @gettimeofday(i8*, i8*)
declare double @sqrt(double)
declare i8* @malloc(i64)
declare i32 @rand()
declare void @srand(i32)
declare i64 @strlen(i8*)
declare i8* @strcpy(i8*, i8*)
declare i8* @strcat(i8*, i8*)
declare void @GC_init()
declare i8* @GC_malloc(i64)
declare double @sin(double)
declare double @cos(double)
declare double @tan(double)
declare double @atan(double)
declare double @atan2(double, double)
declare double @log(double)
declare double @log10(double)
declare double @exp(double)
declare double @pow(double, double)
declare double @floor(double)
declare double @ceil(double)
declare double @fabs(double)
declare i32 @sprintf(i8*, i8*, ...)
declare void @exit(i32)
declare i32 @strcmp(i8*, i8*)
declare i8* @strncpy(i8*, i8*, i64)
declare i32 @toupper(i32)
declare i32 @tolower(i32)
declare i64 @read(i32, i8*, i64)
declare i8* @fopen(i8*, i8*)
declare i32 @fclose(i8*)
declare i32 @fseek(i8*, i64, i32)
declare i64 @ftell(i8*)
declare i64 @fread(i8*, i64, i64, i8*)
declare i64 @fwrite(i8*, i64, i64, i8*)
@fmt_int = private unnamed_addr constant [5 x i8] c"%ld\0A\00"
@fmt_float = private unnamed_addr constant [4 x i8] c"%f\0A\00"
@fmt_str = private unnamed_addr constant [4 x i8] c"%s\0A\00"
@fmt_scan = private unnamed_addr constant [4 x i8] c"%ld\00"
@fmt_int_raw = private unnamed_addr constant [4 x i8] c"%ld\00"
@fmt_float_raw = private unnamed_addr constant [3 x i8] c"%f\00"
@fmt_uncaught = private unnamed_addr constant [25 x i8] c"Excecao nao tratada: %s\0A\00"
@fmt_mode_r = private unnamed_addr constant [2 x i8] c"r\00"
@fmt_mode_w = private unnamed_addr constant [2 x i8] c"w\00"
@fmt_mode_a = private unnamed_addr constant [2 x i8] c"a\00"
@__ares_exc_flag = global i32 0
@__ares_exc_msg = global i8* null


@.str.3 = private unnamed_addr constant [3 x i8] c"A\0A\00"
@.str.4 = private unnamed_addr constant [5 x i8] c"A\09B\0A\00"
@.str.5 = private unnamed_addr constant [5 x i8] c"A\0AB\0A\00"
@.str.6 = private unnamed_addr constant [5 x i8] c"A\5CB\0A\00"
define i32 @main() {
entry:
  call void @GC_init()
  %st_tv_2 = alloca [16 x i8], align 8
  %st_tp_2 = getelementptr [16 x i8], [16 x i8]* %st_tv_2, i32 0, i32 0
  call i32 @gettimeofday(i8* %st_tp_2, i8* null)
  %st_up_2 = getelementptr i8, i8* %st_tp_2, i32 8
  %st_up6_2 = bitcast i8* %st_up_2 to i64*
  %st_uv_2 = load i64, i64* %st_up6_2
  %seed_2 = trunc i64 %st_uv_2 to i32
  call void @srand(i32 %seed_2)
  %pf_3 = getelementptr [3 x i8], [3 x i8]* @.str.3, i32 0, i32 0
  call i32 (i8*, ...) @printf(i8* %pf_3)
  %pf_4 = getelementptr [5 x i8], [5 x i8]* @.str.4, i32 0, i32 0
  call i32 (i8*, ...) @printf(i8* %pf_4)
  %pf_5 = getelementptr [5 x i8], [5 x i8]* @.str.5, i32 0, i32 0
  call i32 (i8*, ...) @printf(i8* %pf_5)
  %pf_6 = getelementptr [5 x i8], [5 x i8]* @.str.6, i32 0, i32 0
  call i32 (i8*, ...) @printf(i8* %pf_6)
  %cast_8 = trunc i64 0 to i32
  ret i32 %cast_8
unreachable_9:
  ret i32 0
func_exc_exit_1:
  %excmsg_top_10 = load i8*, i8** @__ares_exc_msg
  %fmtp_10 = getelementptr [25 x i8], [25 x i8]* @fmt_uncaught, i32 0, i32 0
  call i32 (i8*, ...) @printf(i8* %fmtp_10, i8* %excmsg_top_10)
  call void @exit(i32 1)
  unreachable
}