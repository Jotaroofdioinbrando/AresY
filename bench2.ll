declare i32 @printf(i8*, ...)
declare i32 @scanf(i8*, ...)
declare i32 @gettimeofday(i8*, i8*)
declare double @sqrt(double)
declare i8* @malloc(i64)
declare i32 @rand()
declare void @srand(i32)
@fmt_int = private unnamed_addr constant [5 x i8] c"%ld\0A\00"
@fmt_float = private unnamed_addr constant [4 x i8] c"%f\0A\00"
@fmt_scan = private unnamed_addr constant [4 x i8] c"%ld\00"


define i32 @main() {
entry:
  %st_tv_1 = alloca [16 x i8], align 8
  %st_tp_1 = getelementptr [16 x i8], [16 x i8]* %st_tv_1, i32 0, i32 0
  call i32 @gettimeofday(i8* %st_tp_1, i8* null)
  %st_up_1 = getelementptr i8, i8* %st_tp_1, i32 8
  %st_up6_1 = bitcast i8* %st_up_1 to i64*
  %st_uv_1 = load i64, i64* %st_up6_1
  %seed_1 = trunc i64 %st_uv_1 to i32
  call void @srand(i32 %seed_1)
  %soma = alloca i64, align 8
  store i64 0, i64* %soma, align 8
  %i = alloca i64, align 8
  store i64 0, i64* %i, align 8
  br label %c_4
c_4:
  %reg_6 = load i64, i64* %i, align 8
  %cmp_5 = icmp slt i64 %reg_6, 500000000
  br i1 %cmp_5, label %bt_4, label %be_4
bt_4:
  %reg_9 = load i64, i64* %soma, align 8
  %reg_10 = load i64, i64* %i, align 8
  %tmp_8 = add nsw i64 %reg_9, %reg_10
  store i64 %tmp_8, i64* %soma, align 8
  %reg_12 = load i64, i64* %i, align 8
  %tmp_11 = add nsw i64 %reg_12, 1
  store i64 %tmp_11, i64* %i, align 8
  br label %c_4
be_4:
  %reg_14 = load i64, i64* %soma, align 8
  %pf_15 = getelementptr [5 x i8], [5 x i8]* @fmt_int, i32 0, i32 0
  call i32 (i8*, ...) @printf(i8* %pf_15, i64 %reg_14)
  %cast_17 = trunc i64 0 to i32
  ret i32 %cast_17
unreachable_18:
  ret i32 0
}